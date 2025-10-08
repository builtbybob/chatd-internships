"""
Discord bot implementation for the chatd-internships bot.

This module handles Discord interactions and event handling.
"""

import asyncio
import heapq
import logging
from datetime import datetime
from typing import Dict, List, Any, Set, Optional, Tuple
import time
from enum import Enum
from collections import defaultdict, deque

import aiohttp
import discord
from discord.ext import commands
import schedule

from chatd.config import config
from chatd.messages import format_message
from chatd.repo import clone_or_update_repo, read_json
from chatd.storage_abstraction import DataStorage

# Get logger
logger = logging.getLogger(__name__)


class ReactionFailureType(Enum):
    """Classification of different reaction failure types for appropriate handling."""
    RATE_LIMITED = "rate_limited"      # 429 errors - retry with longer delay
    NETWORK_ERROR = "network_error"    # Connection issues - retry normally
    PERMANENT_ERROR = "permanent"      # 403/404 - don't retry
    SERVER_ERROR = "server_error"      # 5xx errors - retry with backoff
    UNKNOWN_ERROR = "unknown"          # Other errors - limited retry


class ReactionQueue:
    """
    Manages background processing of Discord reactions with rate limiting and retry logic.
    Section 4.4: Enhanced with failure classification, health monitoring, and graceful degradation.
    """
    
    def __init__(self):
        """Initialize the reaction queue with enhanced monitoring."""
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.processor_task: Optional[asyncio.Task] = None
        
        # Basic statistics (Section 4.3)
        self.stats = {
            'queued': 0,
            'processed': 0,
            'failed': 0,
            'retried': 0
        }
        
        # Section 4.4: Enhanced health monitoring and failure handling
        self.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,  # Start with perfect health
            'failure_rate_window': deque(maxlen=config.health_window_size),  # Rolling window for failure rate
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Health monitoring configuration
        self.failure_rate_window_size = 50  # Track last 50 attempts for health calculation
        self.degradation_threshold = 0.5   # 50% failure rate triggers degradation
        self.recovery_threshold = 0.2      # 20% failure rate allows recovery
        self.circuit_breaker_threshold = 10  # Consecutive failures to trigger circuit breaker
    
    async def start(self):
        """Start the background reaction processor."""
        if self.is_running:
            return
        
        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_reactions())
        logger.debug("ReactionQueue processor started")
    
    async def stop(self):
        """Stop the background reaction processor."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
        
        logger.debug("ReactionQueue processor stopped")
    
    def _classify_failure(self, exception: Exception) -> ReactionFailureType:
        """
        Classify the type of failure for appropriate handling strategy.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            ReactionFailureType: Classification of the failure
        """
        if isinstance(exception, discord.NotFound):
            return ReactionFailureType.PERMANENT_ERROR
        elif isinstance(exception, discord.Forbidden):
            return ReactionFailureType.PERMANENT_ERROR
        elif isinstance(exception, discord.HTTPException):
            if exception.status == 429:  # Rate limited
                return ReactionFailureType.RATE_LIMITED
            elif 500 <= exception.status < 600:  # Server errors
                return ReactionFailureType.SERVER_ERROR
            else:
                return ReactionFailureType.NETWORK_ERROR
        elif isinstance(exception, (aiohttp.ClientError, asyncio.TimeoutError)):
            return ReactionFailureType.NETWORK_ERROR
        else:
            return ReactionFailureType.UNKNOWN_ERROR
    
    def _update_health_metrics(self, success: bool, failure_type: Optional[ReactionFailureType] = None):
        """
        Update health monitoring metrics based on reaction attempt result.
        
        Args:
            success: Whether the reaction was successful
            failure_type: Type of failure if unsuccessful
        """
        self.enhanced_stats['total_attempts'] += 1
        
        if success:
            self.enhanced_stats['successful_reactions'] += 1
            self.enhanced_stats['consecutive_failures'] = 0
            self.enhanced_stats['failure_rate_window'].append(False)
        else:
            self.enhanced_stats['failed_reactions'] += 1
            self.enhanced_stats['consecutive_failures'] += 1
            self.enhanced_stats['last_failure_time'] = time.time()
            self.enhanced_stats['failure_rate_window'].append(True)
            
            if failure_type:
                self.enhanced_stats['failure_by_type'][failure_type.value] += 1
        
        # Maintain rolling window size
        if len(self.enhanced_stats['failure_rate_window']) > config.health_window_size:
            self.enhanced_stats['failure_rate_window'].pop(0)
        
        # Calculate health score
        self._calculate_health_score()
        
        # Check for degradation mode changes
        self._check_degradation_mode()
    
    def _calculate_health_score(self):
        """Calculate current health score based on recent failure rate."""
        if not self.enhanced_stats['failure_rate_window']:
            self.enhanced_stats['health_score'] = 1.0
            return
        
        failure_count = sum(self.enhanced_stats['failure_rate_window'])
        total_count = len(self.enhanced_stats['failure_rate_window'])
        failure_rate = failure_count / total_count
        
        # Health score is inverse of failure rate
        self.enhanced_stats['health_score'] = max(0.0, 1.0 - failure_rate)
    
    def _check_degradation_mode(self):
        """Check if degradation mode should be activated or deactivated."""
        failure_rate = self._get_current_failure_rate()
        
        if not self.enhanced_stats['degraded_mode'] and failure_rate >= config.degradation_threshold:
            self.enhanced_stats['degraded_mode'] = True
            self.enhanced_stats['degradation_events'] += 1
            logger.warning(f"🚨 Entering degraded mode due to {failure_rate:.1%} failure rate")
            
        elif self.enhanced_stats['degraded_mode'] and failure_rate <= config.recovery_threshold:
            self.enhanced_stats['degraded_mode'] = False
            logger.info(f"✅ Exiting degraded mode - failure rate improved to {failure_rate:.1%}")
    
    def _get_current_failure_rate(self) -> float:
        """Get current failure rate from rolling window."""
        if not self.enhanced_stats['failure_rate_window']:
            return 0.0
        
        failure_count = sum(self.enhanced_stats['failure_rate_window'])
        total_count = len(self.enhanced_stats['failure_rate_window'])
        return failure_count / total_count
    
    def _should_circuit_break(self) -> bool:
        """Check if circuit breaker should activate due to consecutive failures."""
        # Check if we're in circuit breaker timeout period
        if (self.enhanced_stats['last_failure_time'] and 
            self.enhanced_stats['consecutive_failures'] >= config.circuit_breaker_threshold):
            # Check if timeout period has elapsed
            time_since_last_failure = time.time() - self.enhanced_stats['last_failure_time']
            if time_since_last_failure < config.circuit_breaker_timeout:
                return True  # Still in circuit breaker timeout
            else:
                # Timeout expired - reset consecutive failures to allow retry
                self.enhanced_stats['consecutive_failures'] = 0
                logger.info(f"Circuit breaker timeout expired after {config.circuit_breaker_timeout}s - allowing retry")
                return False
        
        return self.enhanced_stats['consecutive_failures'] >= config.circuit_breaker_threshold
    
    def _get_retry_delay(self, failure_type: ReactionFailureType, retry_count: int) -> float:
        """
        Calculate retry delay based on failure type and retry count.
        
        Args:
            failure_type: Type of failure that occurred
            retry_count: Current retry attempt number
            
        Returns:
            Delay in seconds before retry
        """
        base_delay = config.reaction_retry_delay
        
        if failure_type == ReactionFailureType.PERMANENT_ERROR:
            # No retry for permanent errors (forbidden, not found, etc.)
            return 0.0
        elif failure_type == ReactionFailureType.RATE_LIMITED:
            # Longer delays for rate limits
            return min(base_delay * (3 ** retry_count), 30.0)
        elif failure_type == ReactionFailureType.SERVER_ERROR:
            # Exponential backoff for server errors
            return min(base_delay * (2 ** retry_count), 16.0)
        elif failure_type == ReactionFailureType.NETWORK_ERROR:
            # Standard exponential backoff for network issues
            return min(base_delay * (2 ** retry_count), 8.0)
        else:
            # Conservative retry for unknown errors
            return min(base_delay * (1.5 ** retry_count), 5.0)
    
    async def queue_reactions(self, message: discord.Message, reactions: List[str]) -> None:
        """
        Queue reactions for a message to be processed in the background.
        
        Args:
            message: The Discord message to add reactions to
            reactions: List of reaction emojis to add
        """
        reaction_task = {
            'message': message,
            'reactions': reactions,
            'timestamp': time.time(),
            'retry_count': 0
        }
        
        await self.task_queue.put(reaction_task)
        self.stats['queued'] += 1
        logger.debug(f"Queued {len(reactions)} reactions for message {message.id}")
    
    async def _process_reactions(self):
        """Background task processor for reaction queue."""
        logger.debug("Starting reaction queue processor")
        
        while self.is_running:
            try:
                # Wait for reaction tasks with timeout
                try:
                    reaction_task = await asyncio.wait_for(
                        self.task_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue  # Continue the loop to check if we should stop
                
                # Process the reaction task
                await self._process_single_reaction_task(reaction_task)
                
                # Rate limiting delay between reaction processing
                await asyncio.sleep(config.batch_processing_delay)
                
            except asyncio.CancelledError:
                logger.debug("Reaction processor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in reaction processor: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
    
    async def _process_single_reaction_task(self, reaction_task: Dict[str, Any]):
        """
        Process a single reaction task with enhanced failure handling, monitoring and degradation.
        Section 4.4: Enhanced with failure classification, health monitoring, and circuit breaker.
        
        Args:
            reaction_task: Dictionary containing message, reactions, and metadata
        """
        message = reaction_task['message']
        reactions = reaction_task['reactions']
        retry_count = reaction_task['retry_count']
        
        # Circuit breaker check
        if self._should_circuit_break():
            logger.error(f"🚨 Circuit breaker activated - skipping reactions for message {message.id}")
            self._update_health_metrics(False, ReactionFailureType.PERMANENT_ERROR)
            self.stats['failed'] += len(reactions)
            return
        
        # Degraded mode - use simplified reaction set
        if self.enhanced_stats['degraded_mode']:
            reactions = ['👍']  # Only use simple reactions in degraded mode
            logger.debug(f"Operating in degraded mode - using simplified reactions for message {message.id}")
        
        try:
            # Section 4.3: Process reactions in batches for improved performance
            batch_size = config.reaction_batch_size
            failed_reactions = []
            failed_reaction_types = []
            
            logger.debug(f"Processing {len(reactions)} reactions in batches of {batch_size} for message {message.id}")
            
            # Process reactions in batches
            for i in range(0, len(reactions), batch_size):
                batch = reactions[i:i + batch_size]
                batch_failures = []
                batch_failure_types = []
                
                logger.debug(f"Processing batch {i//batch_size + 1}: {len(batch)} reactions")
                
                # Process current batch rapidly (no delays within batch)
                for reaction in batch:
                    try:
                        await message.add_reaction(reaction)
                        logger.debug(f"Successfully added reaction {reaction} to message {message.id}")
                        self._update_health_metrics(True)
                        
                    except discord.NotFound:
                        logger.warning(f"Message {message.id} not found when adding reaction {reaction}")
                        # Section 4.4: Enhanced early termination with health tracking
                        failure_type = self._classify_failure(discord.NotFound())
                        self._update_health_metrics(False, failure_type)
                        return
                    
                    except discord.Forbidden:
                        logger.warning(f"No permission to add reaction {reaction} to message {message.id}")
                        # Section 4.4: Enhanced early termination with health tracking
                        failure_type = self._classify_failure(discord.Forbidden())
                        self._update_health_metrics(False, failure_type)
                        return
                        
                    except Exception as e:
                        # Section 4.4: Enhanced error classification and handling
                        failure_type = self._classify_failure(e)
                        self._update_health_metrics(False, failure_type)
                        
                        if failure_type == ReactionFailureType.PERMANENT_ERROR:
                            logger.warning(f"Permanent error adding reaction {reaction} to message {message.id}: {e}")
                            return  # Stop processing for permanent errors
                        else:
                            logger.warning(f"Recoverable error adding reaction {reaction} to message {message.id}: {e}")
                            batch_failures.append(reaction)
                            batch_failure_types.append(failure_type)
                
                # Add batch failures to overall failed reactions
                failed_reactions.extend(batch_failures)
                failed_reaction_types.extend(batch_failure_types)
                
                # Delay between batches (but not after the last batch)
                if i + batch_size < len(reactions):
                    logger.debug(f"Batch {i//batch_size + 1} complete, waiting {config.reaction_batch_delay}s before next batch")
                    await asyncio.sleep(config.reaction_batch_delay)
                else:
                    logger.debug(f"Final batch {i//batch_size + 1} complete for message {message.id}")
            
            # Section 4.4: Enhanced retry logic with failure-type-specific delays
            if failed_reactions and retry_count < config.reaction_retry_count:
                # Determine the most severe failure type for retry delay calculation
                most_severe_failure = max(failed_reaction_types, 
                                       key=lambda ft: [ReactionFailureType.RATE_LIMITED, 
                                                     ReactionFailureType.SERVER_ERROR,
                                                     ReactionFailureType.NETWORK_ERROR,
                                                     ReactionFailureType.UNKNOWN_ERROR].index(ft) 
                                       if ft in [ReactionFailureType.RATE_LIMITED, 
                                               ReactionFailureType.SERVER_ERROR,
                                               ReactionFailureType.NETWORK_ERROR,
                                               ReactionFailureType.UNKNOWN_ERROR] else 0)
                
                retry_task = {
                    'message': message,
                    'reactions': failed_reactions,
                    'timestamp': time.time(),
                    'retry_count': retry_count + 1
                }
                
                # Section 4.4: Failure-type-specific retry delay
                retry_delay = self._get_retry_delay(most_severe_failure, retry_count)
                logger.debug(f"Scheduling retry for {len(failed_reactions)} failed reactions in {retry_delay:.1f}s "
                           f"(attempt {retry_count + 1}, failure type: {most_severe_failure.value})")
                await asyncio.sleep(retry_delay)
                
                await self.task_queue.put(retry_task)
                self.stats['retried'] += 1
                self.enhanced_stats['avg_retry_count'] = (self.enhanced_stats['avg_retry_count'] * self.stats['processed'] + (retry_count + 1)) / (self.stats['processed'] + 1)
                logger.debug(f"Retrying {len(failed_reactions)} failed reactions for message {message.id} (attempt {retry_count + 1})")
            
            elif failed_reactions:
                logger.warning(f"Giving up on {len(failed_reactions)} reactions for message {message.id} after {retry_count} retries")
                self.stats['failed'] += len(failed_reactions)
            
            self.stats['processed'] += 1
            
        except Exception as e:
            logger.error(f"Critical error processing reactions for message {message.id}: {e}")
            failure_type = self._classify_failure(e)
            self._update_health_metrics(False, failure_type)
            self.stats['failed'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current reaction queue statistics including Section 4.4 enhancements."""
        basic_stats = self.stats.copy()
        
        # Add Section 4.4 enhanced statistics
        enhanced_stats = {
            'enhanced_metrics': {
                'total_attempts': self.enhanced_stats['total_attempts'],
                'successful_reactions': self.enhanced_stats['successful_reactions'],
                'failed_reactions': self.enhanced_stats['failed_reactions'],
                'failure_by_type': dict(self.enhanced_stats['failure_by_type']),
                'avg_retry_count': round(self.enhanced_stats['avg_retry_count'], 2),
                'degradation_events': self.enhanced_stats['degradation_events'],
                'health_score': round(self.enhanced_stats['health_score'], 3),
                'current_failure_rate': round(self._get_current_failure_rate(), 3),
                'consecutive_failures': self.enhanced_stats['consecutive_failures'],
                'degraded_mode': self.enhanced_stats['degraded_mode'],
                'last_failure_time': self.enhanced_stats['last_failure_time']
            }
        }
        
        return {**basic_stats, **enhanced_stats}
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a concise health summary for monitoring dashboards."""
        return {
            'health_score': round(self.enhanced_stats['health_score'], 3),
            'failure_rate': round(self._get_current_failure_rate(), 3),
            'degraded_mode': self.enhanced_stats['degraded_mode'],
            'consecutive_failures': self.enhanced_stats['consecutive_failures'],
            'circuit_breaker_active': self._should_circuit_break(),
            'total_attempts': self.enhanced_stats['total_attempts'],
            'success_rate': round(
                self.enhanced_stats['successful_reactions'] / max(1, self.enhanced_stats['total_attempts']), 
                3
            )
        }
    
    def _get_current_failure_rate(self) -> float:
        """Calculate current failure rate from rolling window."""
        if not self.enhanced_stats['failure_rate_window']:
            return 0.0
        
        return len([f for f in self.enhanced_stats['failure_rate_window'] if f]) / len(self.enhanced_stats['failure_rate_window'])
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker - useful for administrative control."""
        self.enhanced_stats['consecutive_failures'] = 0
        self.enhanced_stats['degraded_mode'] = False
        self.enhanced_stats['last_failure_time'] = None
        self.logger.info("Circuit breaker manually reset")
    
    def log_health_summary(self):
        """Log periodic health summary for monitoring."""
        health_summary = self.get_health_summary()
        
        if health_summary['degraded_mode']:
            self.logger.warning(f"🚨 Health Check - DEGRADED MODE: {health_summary}")
        elif health_summary['health_score'] < 0.8:
            self.logger.warning(f"⚠️  Health Check - POOR HEALTH: {health_summary}")
        else:
            self.logger.info(f"✅ Health Check - GOOD: {health_summary}")
        
        return health_summary


# Global reaction queue instance
reaction_queue = ReactionQueue()

# Storage will be initialized lazily to avoid import-time directory creation
storage = None

def get_storage():
    """Get or initialize the storage instance."""
    global storage
    if storage is None:
        storage = DataStorage(config)
    return storage

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
            get_storage().add_message_tracking(role_key, str(sent_message.id), channel_id)
        
        # Reset failure count on success
        if channel_id in channel_failure_counts:
            del channel_failure_counts[channel_id]
        
        await asyncio.sleep(config.message_post_delay)  # Configurable rate limiting delay
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
    Queue reactions for a Discord message to be processed in the background.
    This function returns immediately without blocking.
    
    Args:
        message: The Discord message to add reactions to
    """
    # Define reactions to add
    reactions = ['❓', '✅']
    
    # Queue the reactions for background processing
    await reaction_queue.queue_reactions(message, reactions)
    logger.debug(f"Queued reactions for message {message.id}")


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
        results = get_storage().process_job_changes(new_data)
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
    message_tracking = get_storage().get_message_tracking()
    
    # For each job in message tracking, check if the message ID matches
    for job_id, tracking_info in message_tracking.items():
        if tracking_info.get('message_id') == message_id:
            # Find the corresponding role data
            for role in all_data:
                if role['id'] == job_id:
                    return role
    
    return None


async def get_company_jobs_from_database(company_name: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get all recent jobs from a company using database queries.
    
    Args:
        company_name: The company name to search for
        days: Number of days back to search (default: 7)
        
    Returns:
        List[Dict[str, Any]]: List of job postings from the company
    """
    try:
        storage = get_storage()
        
        # If we're using database storage, use optimized SQL queries
        if hasattr(storage, 'database_backend') and storage.database_backend:
            from chatd.database import DatabaseManager
            
            # Calculate cutoff timestamp
            cutoff_timestamp = int(time.time() - (days * 24 * 3600))
            
            # Get database manager
            db_manager = storage.database_backend.db_manager
            
            with db_manager.get_session() as session:
                # Query for jobs from this company
                from chatd.database import JobPosting, JobLocation, JobTerm
                from sqlalchemy import and_
                
                jobs_query = session.query(JobPosting).filter(
                    and_(
                        JobPosting.company_name.ilike(f'%{company_name}%'),
                        JobPosting.active == True,
                        JobPosting.is_visible == True,
                        JobPosting.date_posted >= cutoff_timestamp
                    )
                ).order_by(JobPosting.date_posted.desc())
                
                jobs = []
                for job in jobs_query.all():
                    # Convert ORM object to dictionary
                    job_dict = {
                        'id': str(job.id),
                        'company_name': job.company_name,
                        'title': job.title,
                        'url': job.url,
                        'sponsorship': job.sponsorship,
                        'active': job.active,
                        'source': job.source,
                        'date_posted': job.date_posted,
                        'company_url': job.company_url,
                        'is_visible': job.is_visible,
                        'date_updated': job.date_updated
                    }
                    
                    # Get locations
                    locations = session.query(JobLocation.location).filter(
                        JobLocation.id == job.id
                    ).all()
                    job_dict['locations'] = [loc[0] for loc in locations]
                    
                    # Get terms
                    terms = session.query(JobTerm.term).filter(
                        JobTerm.id == job.id
                    ).all()
                    job_dict['terms'] = [term[0] for term in terms]
                    
                    jobs.append(job_dict)
                
                logger.debug(f"Found {len(jobs)} jobs for company '{company_name}' via database query")
                return jobs
        
        # Fallback to JSON data search
        all_jobs = storage.get_job_postings()
        cutoff_timestamp = int(time.time() - (days * 24 * 3600))
        
        company_jobs = []
        for job in all_jobs:
            if (job.get('company_name', '').lower() == company_name.lower() and
                job.get('active', True) and
                job.get('is_visible', True) and
                job.get('date_posted', 0) >= cutoff_timestamp):
                company_jobs.append(job)
        
        # Sort by date_posted descending
        company_jobs.sort(key=lambda x: x.get('date_posted', 0), reverse=True)
        
        logger.debug(f"Found {len(company_jobs)} jobs for company '{company_name}' via JSON search")
        return company_jobs
        
    except Exception as e:
        logger.error(f"Error fetching company jobs for '{company_name}': {e}")
        return []


async def send_enhanced_company_info_dm(user: discord.Member, role_data: Dict[str, Any]) -> None:
    """
    Send an enhanced DM with comprehensive company information.
    
    Args:
        user: The Discord user to send the DM to
        role_data: The original job role data that triggered the reaction
    """
    try:
        company_name = role_data.get('company_name', '')
        if not company_name:
            # Fallback to individual job info
            await send_dm_with_job_info(user, role_data)
            return
        
        # Get all recent jobs from this company
        company_jobs = await get_company_jobs_from_database(company_name, days=7)
        
        if not company_jobs:
            # Fallback to individual job info if no company data found
            await send_dm_with_job_info(user, role_data)
            return
        
        # Build enhanced company info message
        dm_message = [
            f"# 🏢 {company_name} - Company Overview",
            "",
            f"Here's comprehensive information about **{company_name}** and their current opportunities:",
            "",
            f"**📊 Total Active Positions:** {len(company_jobs)}",
        ]
        
        # Collect unique locations and terms
        all_locations = set()
        all_terms = set()
        for job in company_jobs:
            all_locations.update(job.get('locations', []))
            all_terms.update(job.get('terms', []))
        
        if all_locations:
            locations_str = ', '.join(sorted(all_locations)[:5])  # Limit to 5 locations
            if len(all_locations) > 5:
                locations_str += f" and {len(all_locations) - 5} more"
            dm_message.append(f"**📍 Locations:** {locations_str}")
        
        if all_terms:
            terms_str = ', '.join(sorted(all_terms)[:3])  # Limit to 3 terms
            if len(all_terms) > 3:
                terms_str += f" and {len(all_terms) - 3} more"
            dm_message.append(f"**📅 Terms:** {terms_str}")
        
        dm_message.extend([
            "",
            "## 💼 Current Opportunities",
            ""
        ])
        
        # List up to 10 jobs
        max_jobs_shown = min(10, len(company_jobs))
        for i, job in enumerate(company_jobs[:max_jobs_shown]):
            title = job.get('title', 'Not specified')
            url = job.get('url', '')
            locations = job.get('locations', [])
            location_str = ', '.join(locations[:2]) if locations else 'Remote/Multiple'
            if len(locations) > 2:
                location_str += f" +{len(locations) - 2} more"
            
            dm_message.append(f"**{i+1}. {title}**")
            dm_message.append(f"   📍 {location_str}")
            if url:
                dm_message.append(f"   🔗 [Apply Here]({url})")
            dm_message.append("")
        
        if len(company_jobs) > max_jobs_shown:
            dm_message.append(f"*...and {len(company_jobs) - max_jobs_shown} more positions*")
            dm_message.append("")
        
        # Add footer
        dm_message.extend([
            "---",
            "",
            "💡 **Tip:** Apply to multiple positions at the same company to increase your chances!",
            "",
            "🚀 **Good luck with your applications!**"
        ])
        
        # Send the enhanced DM
        await user.send("\n".join(dm_message))
        logger.info(f"Sent enhanced company info DM for {company_name} to {user.display_name}#{user.discriminator} ({len(company_jobs)} jobs)")
        
    except Exception as e:
        logger.error(f"Failed to send enhanced company info DM to {user.display_name}#{user.discriminator}: {e}")
        # Fallback to individual job info
        try:
            await send_dm_with_job_info(user, role_data)
        except Exception as fallback_error:
            logger.error(f"Fallback DM also failed: {fallback_error}")


@bot.event
async def on_ready() -> None:
    """
    Event handler for when the bot is ready.
    """
    logger.info(f'Logged in as {bot.user}')
    logger.info(f'Bot is ready and monitoring {len(config.channel_ids)} channels')

    # Start the reaction queue processor
    await reaction_queue.start()

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
    
    # Stop the reaction queue processor
    await reaction_queue.stop()
    
    # Log reaction queue statistics
    stats = reaction_queue.get_stats()
    logger.info(f"Reaction queue stats - Queued: {stats['queued']}, "
               f"Processed: {stats['processed']}, Failed: {stats['failed']}, "
               f"Retried: {stats['retried']}")
    
    # Try to close any remaining HTTP sessions
    try:
        if hasattr(bot, 'http') and hasattr(bot.http, 'session'):
            if not bot.http.session.closed:
                await bot.http.session.close()
                logger.debug("Discord HTTP session closed")
    except Exception as e:
        logger.debug(f"Note: HTTP session cleanup issue (non-critical): {e}")


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User) -> None:
    """
    Event handler for when a reaction is added to a message.
    Enhanced with selective processing - only ❓ reactions trigger company info.
    
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
    
    # Section 5.1: Selective processing - only respond to ❓ reactions
    if str(reaction.emoji) != '❓':
        logger.debug(f"Ignoring non-❓ reaction {reaction.emoji} from {user.display_name}")
        return
    
    logger.debug(f"Processing ❓ reaction from {user.display_name} on message {message.id}")
    
    # Get role data by message ID
    role_data = await get_role_data_by_message_id(str(message.id))
    
    if role_data:
        # Section 5.2: Send enhanced company info instead of individual job info
        if isinstance(user, discord.Member):  # Only discord.Member objects have DM capabilities
            await send_enhanced_company_info_dm(user, role_data)
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
            logger.info("Starting bot cleanup...")
            
            # Stop the reaction queue processor
            await reaction_queue.stop()
            
            # Close the Discord bot
            if not bot.is_closed():
                await bot.close()
            
            # Give a moment for connections to close
            await asyncio.sleep(0.5)
            
            # Close any remaining aiohttp sessions
            try:
                # Get the current event loop
                loop = asyncio.get_event_loop()
                
                # Close all unclosed aiohttp connectors
                for task in asyncio.all_tasks(loop):
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                
                # Force cleanup of any remaining aiohttp sessions
                await asyncio.sleep(0.1)
                
                logger.info("Bot cleanup completed")
            except Exception as cleanup_error:
                logger.warning(f"Error during session cleanup: {cleanup_error}")
    
    try:
        asyncio.run(run_with_cleanup())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise
