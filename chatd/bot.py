"""
Discord bot implementation for the chatd-internships bot.

This module handles Discord interactions and event handling.
"""

import asyncio
import heapq
from datetime import datetime
from typing import Dict, List, Any, Set, Optional, Tuple

import discord
from discord.ext import commands
import schedule

from chatd.config import config
from chatd.logging_utils import get_logger
from chatd.messages import format_message
from chatd.repo import clone_or_update_repo, read_json
from chatd.storage_abstraction import DataStorage

# Get logger
logger = get_logger()

# Initialize storage
storage = DataStorage(config)

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = config.enable_reactions  # Enable reaction intents only if reactions are enabled
bot = commands.Bot(command_prefix='!', intents=intents)

# Bot state
failed_channels: Set[str] = set()  # Keep track of channels that have failed
channel_failure_counts: Dict[str, int] = {}  # Track failure counts for each channel


async def send_message(message: str, channel_id: str, role_key: Optional[str] = None) -> Optional[discord.Message]:
    """
    Send a message to a Discord channel with error handling and retry mechanism.
    
    Args:
        message: The message content to send
        channel_id: The Discord channel ID
        role_key: Optional role key for tracking messages
        
    Returns:
        Optional[discord.Message]: The sent message if successful, None otherwise
    """
    if channel_id in failed_channels:
        logger.debug(f"Skipping previously failed channel ID {channel_id}")
        return None

    try:
        logger.debug(f"Sending message to channel ID {channel_id}...")
        channel = bot.get_channel(int(channel_id))
        
        if channel is None:
            logger.debug(f"Channel {channel_id} not in cache, attempting to fetch...")
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except discord.NotFound:
                logger.warning(f"Channel {channel_id} not found")
                channel_failure_counts[channel_id] = channel_failure_counts.get(channel_id, 0) + 1
                if channel_failure_counts[channel_id] >= config.max_retries:
                    failed_channels.add(channel_id)
                return None
            except discord.Forbidden:
                logger.error(f"No permission for channel {channel_id}")
                failed_channels.add(channel_id)  # Immediate blacklist on permission issues
                return None
            except Exception as e:
                logger.error(f"Error fetching channel {channel_id}: {e}")
                channel_failure_counts[channel_id] = channel_failure_counts.get(channel_id, 0) + 1
                if channel_failure_counts[channel_id] >= config.max_retries:
                    failed_channels.add(channel_id)
                return None

        sent_message = await channel.send(message)
        logger.debug(f"Successfully sent message to channel {channel_id}")
        
        # Add reactions to the message if enabled
        if config.enable_reactions:
            await add_reactions_to_message(sent_message)
        
        # Store message info if we have a role key
        if role_key:
            storage.add_message_tracking(role_key, str(sent_message.id), channel_id)
        
        # Reset failure count on success
        if channel_id in channel_failure_counts:
            del channel_failure_counts[channel_id]
        
        await asyncio.sleep(1)  # Rate limiting delay
        return sent_message
        
    except Exception as e:
        logger.error(f"Error sending message to channel {channel_id}: {e}")
        channel_failure_counts[channel_id] = channel_failure_counts.get(channel_id, 0) + 1
        if channel_failure_counts[channel_id] >= config.max_retries:
            logger.warning(f"Channel {channel_id} has failed {config.max_retries} times, adding to failed channels")
            failed_channels.add(channel_id)
        return None


async def add_reactions_to_message(message: discord.Message) -> None:
    """
    Add predefined reactions to a Discord message.
    
    Args:
        message: The Discord message to add reactions to
    """
    # Define reactions to add
    reactions = ['❓', '✅']
    
    for reaction in reactions:
        try:
            await message.add_reaction(reaction)
            await asyncio.sleep(0.5)  # Add a small delay between reactions
        except Exception as e:
            logger.warning(f"Failed to add reaction {reaction} to message {message.id}: {e}")


async def send_messages_to_channels(message: str, role_key: Optional[str] = None) -> List[discord.Message]:
    """
    Send a message to multiple Discord channels concurrently with error handling.
    
    Args:
        message: The message content to send
        role_key: Optional role key for tracking messages
        
    Returns:
        List[discord.Message]: List of successfully sent messages
    """
    tasks = []
    for channel_id in config.channel_ids:
        if channel_id not in failed_channels:
            tasks.append(send_message(message, channel_id, role_key))
    
    # Wait for all messages to be sent
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None and exceptions
    return [msg for msg in results if isinstance(msg, discord.Message)]


async def check_for_new_roles() -> None:
    """
    Check for new roles in the repository and process all changes including updates.
    """
    logger.debug("Checking for new roles and updates...")
    
    # Run git operations in a thread pool to avoid blocking the event loop
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        has_updates = await loop.run_in_executor(None, clone_or_update_repo)
    except Exception as e:
        logger.error(f"Error updating repository: {e}")
        return
    
    if not has_updates:
        logger.debug("No updates to listings file, skipping check.")
        return
        
    new_data = read_json()
    
    # Process changes using the new update support
    try:
        results = storage.process_job_changes(new_data)
        logger.info(f"Change processing completed: {results['added_count']} added, "
                   f"{results['updated_count']} updated, {results['removed_count']} removed")
        
        if not results['success']:
            logger.warning(f"Some updates failed: {len(results.get('update_failures', []))} failures")
            for failure in results.get('update_failures', []):
                logger.warning(f"Update failed for job {failure['job_id']}: {failure['reason']}")
                
        # Store the change detection results for Discord processing
        changes_for_discord = results.get('changes_for_discord')
        
    except Exception as e:
        logger.error(f"Error processing job changes: {e}")
        return
    
    # Process new roles for Discord notifications
    if results['added_count'] > 0:
        logger.debug(f"Processing {results['added_count']} new roles for Discord notifications")
        
        # Get added roles from the stored change detection results
        new_roles = changes_for_discord.get('added', []) if changes_for_discord else []
        
        # Initialize a priority queue for new roles
        new_roles_heap = []
        
        for new_role in new_roles:
            # Get boolean values directly since they are stored as proper booleans
            new_active = new_role.get('active', False)
            new_is_visible = new_role.get('is_visible', True)  # Default to True since all existing entries use True
            
            # Check for visible and active roles only
            if new_is_visible and new_active:
                # Check if the role was updated within the configured time period
                days_since_posted = (datetime.now().timestamp() - new_role['date_posted']) / (24 * 60 * 60)
                if days_since_posted <= config.max_post_age_days:
                    # Add to priority queue in chronological order (oldest first)
                    # Using (timestamp, counter) as the key to ensure unique ordering
                    counter = len(new_roles_heap)  # Use length as a unique secondary key
                    heapq.heappush(new_roles_heap, (new_role['date_posted'], counter, new_role))
                    logger.debug(f"New role found: {new_role['title']} at {new_role['company_name']}")
                else:
                    logger.debug(f"Skipping old role: {new_role['title']} at {new_role['company_name']} (posted {days_since_posted:.1f} days ago, max age: {config.max_post_age_days} days)")

        logger.debug(f"Found {len(new_roles_heap)} new roles for Discord notifications, processing in chronological order")

        # Process roles in order (oldest first)
        while new_roles_heap:
            _, _, role = heapq.heappop(new_roles_heap)  # Unpack timestamp, counter, and role
            role_key = role['id']
            message = format_message(role)
            await send_messages_to_channels(message, role_key)
    
    # TODO: Process updated roles for Discord message updates (Phase 17)
    # This will be implemented when section 17 (Discord Message Update Integration) is developed
    if results['updated_count'] > 0:
        logger.debug(f"Detected {results['updated_count']} job updates. Discord message updates will be implemented in Phase 17.")
    
    logger.debug("Job processing completed successfully.")


async def send_dm_with_job_info(user: discord.Member, role_data: Dict[str, Any]) -> None:
    """
    Send a DM to a user with detailed job information.
    
    Args:
        user: The Discord user to send the DM to
        role_data: The role data to include in the DM
    """
    try:
        # Create a more detailed message for DM
        title = role_data.get('title', 'Not specified')
        company = role_data.get('company_name', 'Not specified')
        url = role_data.get('url', '')
        locations = role_data.get('locations', [])
        location_str = ', '.join(locations) if locations else 'Not specified'
        terms = role_data.get('terms', [])
        term_str = ', '.join(terms) if terms else 'Not specified'
        sponsorship = role_data.get('sponsorship', 'Not specified')
        description = role_data.get('description', 'No description available')
        
        # Build the DM message
        dm_message = [
            f"# {company} - {title}",
            "",
            "Thank you for your interest in this position! Here's more information:",
            "",
            f"**Company:** {company}",
            f"**Position:** {title}",
            f"**Locations:** {location_str}",
            f"**Terms:** {term_str}",
            f"**Sponsorship:** {sponsorship}",
            "",
        ]
        
        # Add description if available
        if description:
            dm_message.append("## Description")
            dm_message.append(description[:1500] + "..." if len(description) > 1500 else description)
            dm_message.append("")
        
        # Add application link
        if url:
            dm_message.append("## Apply")
            dm_message.append(f"**Application Link:** {url}")
            dm_message.append("")
            dm_message.append("Good luck with your application!")
        
        # Send the DM
        await user.send("\n".join(dm_message))
        logger.info(f"Sent job details DM to {user.display_name}#{user.discriminator}")
        
    except Exception as e:
        logger.error(f"Failed to send DM to {user.display_name}#{user.discriminator}: {e}")


async def get_role_data_by_message_id(message_id: str) -> Optional[Dict[str, Any]]:
    """
    Get role data by message ID.
    
    Args:
        message_id: The Discord message ID
        
    Returns:
        Optional[Dict[str, Any]]: The role data if found, None otherwise
    """
    # Load all data
    all_data = read_json()
    
    # Get message tracking data
    message_tracking = storage.get_message_tracking()
    
    # For each job in message tracking, check if the message ID matches
    for job_id, tracking_info in message_tracking.items():
        if tracking_info.get('message_id') == message_id:
            # Find the corresponding role data
            for role in all_data:
                if role['id'] == job_id:
                    return role
    
    return None


@bot.event
async def on_ready() -> None:
    """
    Event handler for when the bot is ready.
    """
    logger.info(f'Logged in as {bot.user}')
    logger.info(f'Bot is ready and monitoring {len(config.channel_ids)} channels')

    # Initial check for new roles on startup
    await check_for_new_roles()

    # Start the scheduled job loop
    while True:
        schedule.run_pending()  # This will respect the CHECK_INTERVAL_MINUTES setting
        await asyncio.sleep(1)  # Small delay to prevent busy-waiting


@bot.event
async def on_disconnect() -> None:
    """
    Event handler for when the bot disconnects.
    """
    logger.info("Bot is disconnecting...")


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User) -> None:
    """
    Event handler for when a reaction is added to a message.
    
    Args:
        reaction: The reaction that was added
        user: The user who added the reaction
    """
    # Skip if reactions are disabled
    if not config.enable_reactions:
        return
        
    # Ignore bot's own reactions
    if user.id == bot.user.id:
        return
    
    # Get the message and channel
    message = reaction.message
    
    # Check if this is a bot message (we only process reactions to our own messages)
    if message.author.id != bot.user.id:
        return
    
    logger.debug(f"Reaction {reaction.emoji} added by {user.display_name} to message {message.id}")
    
    # Get role data by message ID
    role_data = await get_role_data_by_message_id(str(message.id))
    
    if role_data:
        # Send DM with job details
        if isinstance(user, discord.Member):  # Only discord.Member objects have DM capabilities
            await send_dm_with_job_info(user, role_data)
        else:
            logger.warning(f"User {user.id} is not a Member, cannot send DM")
    else:
        logger.warning(f"Could not find role data for message {message.id}")


def run_check_for_new_roles() -> None:
    """
    Wrapper to run the async check_for_new_roles in the bot's event loop.
    """
    if bot.loop and bot.loop.is_running():
        bot.loop.create_task(check_for_new_roles())
    else:
        logger.warning("Bot event loop is not running, skipping scheduled check")


def setup_scheduler() -> None:
    """Set up the scheduler for periodic checks."""
    schedule.every(config.check_interval_minutes).minutes.do(run_check_for_new_roles)
    logger.info(f"Scheduled job to check for new roles every {config.check_interval_minutes} minutes")


def run_bot() -> None:
    """Run the Discord bot."""
    logger.info("Starting bot with environment configuration...")
    logger.info(f"Monitoring {len(config.channel_ids)} channels every {config.check_interval_minutes} minutes")
    
    # Set up scheduler
    setup_scheduler()
    
    # Run the bot with proper cleanup
    async def run_with_cleanup():
        """Run bot with proper session cleanup."""
        try:
            await bot.start(config.discord_token)
        finally:
            await bot.close()
    
    try:
        asyncio.run(run_with_cleanup())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise
