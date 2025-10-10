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
            'total_queued': 0,      # Total tasks ever queued
            'processed': 0,         # Total tasks completed
            'failed': 0,            # Total tasks failed
            'retried': 0           # Total retry attempts
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
        logger.debug(f"🚀 ReactionQueue.start() called - currently running: {self.is_running}")
        
        if self.is_running:
            logger.warning("⚠️ ReactionQueue already running, skipping start")
            return
        
        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_reactions())
        logger.info("✅ ReactionQueue processor started successfully")
    
    async def stop(self):
        """Stop the background reaction processor."""
        logger.debug(f"🛑 ReactionQueue.stop() called - currently running: {self.is_running}")
        
        if not self.is_running:
            logger.debug("⚠️ ReactionQueue already stopped")
            return
        
        self.is_running = False
        
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                logger.debug("ReactionQueue processor task cancelled")
            self.processor_task = None
        
        logger.info("✅ ReactionQueue processor stopped")
    
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
        self.stats['total_queued'] += 1
        
        # Get current queue size for more accurate logging
        current_queue_size = self.task_queue.qsize()
        logger.info(f"📤 Queued {len(reactions)} reactions for message {message.id} "
                   f"(queue size: {current_queue_size}, total queued: {self.stats['total_queued']})")
    
    async def _process_reactions(self):
        """Background task processor for reaction queue."""
        logger.info("🚀 Starting reaction queue processor task")
        
        while self.is_running:
            try:
                # Wait for reaction tasks with timeout
                try:
                    logger.debug("Waiting for reaction tasks in queue...")
                    reaction_task = await asyncio.wait_for(
                        self.task_queue.get(), 
                        timeout=1.0
                    )
                    logger.info(f"📥 Received reaction task for message {reaction_task['message'].id}")
                except asyncio.TimeoutError:
                    logger.debug("No reaction tasks in queue, continuing...")
                    continue  # Continue the loop to check if we should stop
                
                # Process the reaction task
                logger.info(f"🔄 Processing reaction task for message {reaction_task['message'].id}")
                await self._process_single_reaction_task(reaction_task)
                logger.info(f"✅ Completed processing reaction task for message {reaction_task['message'].id}")
                
                # Rate limiting delay between reaction processing
                await asyncio.sleep(config.batch_processing_delay)
                
            except asyncio.CancelledError:
                logger.info("❌ Reaction processor cancelled - stopping gracefully")
                break
            except Exception as e:
                logger.error(f"💥 Critical error in reaction processor: {e}", exc_info=True)
                await asyncio.sleep(1)  # Brief pause before retrying
        
        logger.info("🏁 Reaction queue processor task ended")
    
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
                        
                    except discord.NotFound as e:
                        logger.warning(f"Message {message.id} not found when adding reaction {reaction}")
                        # Section 4.4: Enhanced early termination with health tracking
                        failure_type = self._classify_failure(e)
                        self._update_health_metrics(False, failure_type)
                        return
                    
                    except discord.Forbidden as e:
                        logger.warning(f"No permission to add reaction {reaction} to message {message.id}")
                        # Section 4.4: Enhanced early termination with health tracking
                        failure_type = self._classify_failure(e)
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
        
        # Add current queue size for better monitoring
        basic_stats['current_queue_size'] = self.task_queue.qsize()
        
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
    # Use configurable reactions from config
    reactions = config.message_reactions
    
    # Queue the reactions for background processing
    await reaction_queue.queue_reactions(message, reactions)
    logger.debug(f"🎯 Bot queuing reactions {reactions} for message {message.id} (Bot ID: {bot.user.id if bot.user else 'Not initialized'})")


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
    Get role data by message ID using database queries.
    
    Args:
        message_id: The Discord message ID
        
    Returns:
        Optional[Dict[str, Any]]: The role data if found, None otherwise
    """
    # Use storage abstraction to get database backend
    storage = get_storage()
    
    # Check if we have database backend available
    if hasattr(storage, 'database_backend') and storage.database_backend:
        try:
            from chatd.database import JobPosting, MessageTracking
            
            # Get database manager
            db_manager = storage.database_backend.db_manager
            
            with db_manager.session_scope() as session:
                # Query for job posting by message ID, including soft-deleted records
                # Users should still be able to get info about deleted jobs via reactions
                result = session.query(JobPosting).join(MessageTracking).filter(
                    MessageTracking.message_id == message_id
                ).first()
                
                if result:
                    # Convert to dictionary format expected by bot
                    role_data = {
                        'id': str(result.id),
                        'date_updated': result.date_updated,
                        'url': result.url,
                        'company_name': result.company_name,
                        'title': result.title,
                        'sponsorship': result.sponsorship,
                        'active': result.active,
                        'source': result.source,
                        'date_posted': result.date_posted,
                        'company_url': result.company_url,
                        'is_visible': result.is_visible,
                        'category': result.category,
                        'is_deleted': result.is_deleted,
                        'locations': result.location_list,
                        'terms': result.term_list,
                        'degrees': result.degree_list
                    }
                    
                    logger.debug(f"Found role data for message {message_id} via database query (deleted: {result.is_deleted})")
                    return role_data
                else:
                    logger.debug(f"No role data found for message {message_id} in database")
                    return None
                    
        except Exception as e:
            logger.error(f"Database query failed for message {message_id}: {e}")
            # Fall back to JSON approach
    
    # Fallback to JSON approach for compatibility
    logger.debug(f"Using JSON fallback for message {message_id}")
    
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
                        JobPosting.is_deleted == False,
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


async def get_enhanced_company_insights(company_name: str, days: int = 7) -> Dict[str, Any]:
    """
    Get comprehensive company insights with SQL aggregation.
    
    Args:
        company_name: The company name to search for
        days: Number of days to look back for recent jobs (default: 7)
        
    Returns:
        Dictionary containing enhanced company insights:
        - total_positions: Total number of active positions
        - jobs: List of job dictionaries
        - location_analysis: Dictionary with location counts and top locations
        - term_analysis: Dictionary with term counts and breakdown
        - application_deadlines: List of jobs with upcoming deadlines
        - job_families: Jobs grouped by type (intern, new grad, etc.)
    """
    from chatd.config import config
    
    try:
        # Check if company info is enabled
        if not config.enable_company_info:
            return {}
            
        # Use storage abstraction to get database backend
        storage = get_storage()
        if not hasattr(storage, 'database_backend') or not storage.database_backend:
            # Fallback to basic job list
            basic_jobs = await get_company_jobs_from_database(company_name, days)
            return {
                'total_positions': len(basic_jobs),
                'jobs': basic_jobs,
                'location_analysis': {},
                'term_analysis': {},
                'application_deadlines': [],
                'job_families': {'Other': basic_jobs}
            }
            
        # Calculate cutoff timestamp
        cutoff_timestamp = int(time.time() - (days * 24 * 3600))
        
        # Get database manager
        db_manager = storage.database_backend.db_manager
        
        with db_manager.get_session() as session:
            from chatd.database import JobPosting, JobLocation, JobTerm
            from sqlalchemy import and_, func, distinct
            
            # Main query for jobs with JOIN for efficient data retrieval
            jobs_query = session.query(
                JobPosting,
                func.array_agg(distinct(JobLocation.location)).label('locations'),
                func.array_agg(distinct(JobTerm.term)).label('terms')
            ).outerjoin(
                JobLocation, JobPosting.id == JobLocation.id
            ).outerjoin(
                JobTerm, JobPosting.id == JobTerm.id
            ).filter(
                and_(
                    JobPosting.company_name.ilike(f'%{company_name}%'),
                    JobPosting.active == True,
                    JobPosting.is_visible == True,
                    JobPosting.date_posted >= cutoff_timestamp
                )
            ).group_by(JobPosting.id).order_by(JobPosting.date_posted.desc())
            
            # Execute query and build jobs list
            jobs = []
            all_locations = []
            all_terms = []
            
            for result in jobs_query.all():
                job = result.JobPosting
                locations = [loc for loc in (result.locations or []) if loc is not None]
                terms = [term for term in (result.terms or []) if term is not None]
                
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
                    'date_updated': job.date_updated,
                    'locations': locations,
                    'terms': terms
                }
                
                jobs.append(job_dict)
                all_locations.extend(locations)
                all_terms.extend(terms)
            
            # Count total active positions by company (including different filters)
            total_positions = session.query(func.count(JobPosting.id)).filter(
                and_(
                    JobPosting.company_name.ilike(f'%{company_name}%'),
                    JobPosting.active == True,
                    JobPosting.is_visible == True,
                    JobPosting.is_deleted == False
                )
            ).scalar() or 0
            
            # Location analysis with counts
            location_counts = {}
            for location in all_locations:
                if location:
                    location_counts[location] = location_counts.get(location, 0) + 1
            
            # Sort locations by frequency
            top_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
            location_analysis = {
                'total_locations': len(location_counts),
                'location_counts': location_counts,
                'top_locations': top_locations[:5],  # Top 5 locations
                'has_remote': any('remote' in loc.lower() for loc in location_counts.keys())
            }
            
            # Term analysis (internship cycles, etc.)
            term_counts = {}
            for term in all_terms:
                if term:
                    term_counts[term] = term_counts.get(term, 0) + 1
            
            # Sort terms by frequency
            top_terms = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)
            term_analysis = {
                'total_terms': len(term_counts),
                'term_counts': term_counts,
                'top_terms': top_terms[:3],  # Top 3 terms
                'current_cycle': top_terms[0][0] if top_terms else None
            }
            
            # Application deadlines (look for jobs posted recently - they often have near-term deadlines)
            recent_jobs = [job for job in jobs if job['date_posted'] >= (time.time() - 14*24*3600)]  # Last 2 weeks
            application_deadlines = sorted(recent_jobs, key=lambda x: x['date_posted'], reverse=True)[:5]
            
            return {
                'total_positions': total_positions,
                'recent_positions': len(jobs),
                'jobs': jobs,
                'location_analysis': location_analysis,
                'term_analysis': term_analysis,
                'application_deadlines': application_deadlines,
                'company_name': company_name,
                'query_days': days
            }
            
    except Exception as e:
        logger.error(f"Error getting enhanced company insights: {e}")
        # Fallback to basic data
        basic_jobs = await get_company_jobs_from_database(company_name, days)
        return {
            'total_positions': len(basic_jobs),
            'jobs': basic_jobs,
            'location_analysis': {},
            'term_analysis': {},
            'application_deadlines': [],
            'job_families': {'Other': basic_jobs} if basic_jobs else {}
        }


async def send_enhanced_company_info_dm(user: discord.Member, role_data: Dict[str, Any]) -> None:
    """
    Send an enhanced DM with comprehensive company information and rich formatting.
    
    Args:
        user: The Discord user to send the DM to
        role_data: The original job role data that triggered the reaction
    """
    from chatd.config import config
    
    try:
        company_name = role_data.get('company_name', '')
        if not company_name:
            # Fallback to individual job info
            await send_dm_with_job_info(user, role_data)
            return
        
        # Get enhanced company insights with SQL aggregation
        insights = await get_enhanced_company_insights(company_name, days=config.company_info_days)
        
        if not insights or not insights.get('jobs'):
            # Fallback to individual job info if no company data found
            await send_dm_with_job_info(user, role_data)
            return
        
        # Build enhanced company info message with comprehensive data
        dm_message = [
            f"# 🏢 {company_name} - Comprehensive Overview",
            "",
            f"Here's everything you need to know about **{company_name}** and their opportunities:",
            ""
        ]
        
        # Get company URL first for Company Snapshot
        company_url = None
        for job in insights.get('jobs', []):
            if job.get('company_url'):
                company_url = job['company_url']
                break
        
        # Company overview section with job count and locations
        total_positions = insights.get('total_positions', 0)
        recent_positions = insights.get('recent_positions', 0)
        
        dm_message.extend([
            "## 🌐 Company Snapshot",
        ])
        
        # Add company website as first item if available
        if company_url:
            dm_message.append(f"**Company Website:** [Visit {company_name}](<{company_url}>)")
        
        dm_message.extend([
            f"**Total Active Positions:** {total_positions}",
            f"**Recent Postings ({config.company_info_days} days):** {recent_positions}",
        ])
        
        # Location analysis
        location_analysis = insights.get('location_analysis', {})
        if location_analysis.get('top_locations'):
            top_locations = location_analysis['top_locations'][:3]  # Top 3 locations
            location_text = ', '.join([f"{loc} ({count})" for loc, count in top_locations])
            total_locations = location_analysis.get('total_locations', 0)
            
            if total_locations > 3:
                location_text += f" and {total_locations - 3} more locations"
            
            dm_message.append(f"**Top Locations:** {location_text}")
            
            if location_analysis.get('has_remote'):
                dm_message.append("**Remote Work:** Available")
        
        # Term analysis
        term_analysis = insights.get('term_analysis', {})
        if term_analysis.get('top_terms'):
            top_terms = term_analysis['top_terms'][:2]  # Top 2 terms
            terms_text = ', '.join([f"{term} ({count})" for term, count in top_terms])
            dm_message.append(f"**Main Cycles:** {terms_text}")
        
        dm_message.append("")
        
        # Available Positions - simplified approach since dataset is internship-focused
        jobs = insights.get('jobs', [])
        if jobs:
            dm_message.extend([
                f"## 💼 Available Positions ({len(jobs)})",
                ""
            ])
            
            # Show all positions
            for job in jobs:
                title = job.get('title', 'Not specified')
                url = job.get('url', '')
                locations = job.get('locations', [])
                terms = job.get('terms', [])
                sponsorship = job.get('sponsorship', '')
                
                # Format location string with full locations (no truncation)
                location_str = ', '.join(locations) if locations else 'Remote/Multiple'
                
                # Format posting date - concise format
                date_posted = job.get('date_posted', 0)
                if date_posted:
                    import datetime
                    posted_date = datetime.datetime.fromtimestamp(date_posted)
                    days_ago = (datetime.datetime.now() - posted_date).days
                    if days_ago == 0:
                        date_str = "Today"
                    elif days_ago == 1:
                        date_str = "1d ago"
                    else:
                        date_str = f"{days_ago}d ago"
                else:
                    date_str = "Recently"
                
                # Build details line with smart sponsorship
                details_parts = []
                details_parts.append(location_str)
                
                if terms:
                    terms_str = ', '.join(terms)
                    details_parts.append(terms_str)
                
                # Only show sponsorship if it's meaningful (not "Other")
                if sponsorship and sponsorship.lower() != 'other':
                    details_parts.append(f"Sponsored" if 'sponsor' in sponsorship.lower() else sponsorship)
                
                details_parts.append(date_str)
                
                # Check if location line would be too long (>40 chars) for overflow logic
                details_line = ' • '.join(details_parts)
                
                # Section 5.6: Clean two-line format with link preview suppression
                if url:
                    dm_message.append(f"**[{title}](<{url}>)**")  # Suppress previews with angle brackets
                else:
                    dm_message.append(f"**{title}**")
                
                # Handle location overflow logic
                if len(location_str) > 40 and len(locations) > 1:
                    # Multi-line format for long locations
                    dm_message.append(f"   {location_str}")
                    # Build remaining details without location
                    remaining_details = []
                    if terms:
                        remaining_details.append(terms_str)
                    if sponsorship and sponsorship.lower() != 'other':
                        remaining_details.append(f"Sponsored" if 'sponsor' in sponsorship.lower() else sponsorship)
                    remaining_details.append(date_str)
                    if remaining_details:
                        dm_message.append(f"   {' • '.join(remaining_details)}")
                else:
                    # Single line format
                    dm_message.append(f"   {details_line}")
                
                dm_message.append("")
        
        # Section 5.6: Remove duplicate "Recently Posted" section to eliminate redundancy
        
        # Direct links to all company applications (with preview suppression)
        company_url = None
        for job in insights.get('jobs', []):
            if job.get('company_url'):
                company_url = job['company_url']
                break
        
        # Enhanced footer
        dm_message.extend([
            "---",
            "",
            "🚀 **Good luck with your applications!**",
            "",
            f"*This overview covers {recent_positions} recent positions from {company_name}. Data updated every {config.company_info_days} days.*"
        ])
        
        # Send the enhanced DM
        full_message = "\n".join(dm_message)
        
        # Discord has a 2000 character limit, so we may need to split the message
        if len(full_message) <= 2000:
            await user.send(full_message)
        else:
            # Split into multiple messages
            messages = []
            current_message = ""
            
            for line in dm_message:
                if len(current_message) + len(line) + 1 <= 1900:  # Leave some buffer
                    current_message += line + "\n"
                else:
                    if current_message:
                        messages.append(current_message.strip())
                    current_message = line + "\n"
            
            if current_message:
                messages.append(current_message.strip())
            
            # Send each message part
            for i, message_part in enumerate(messages):
                await user.send(message_part)
                if i < len(messages) - 1:
                    await asyncio.sleep(1)  # Small delay between messages
        
        logger.info(f"Sent enhanced company insights DM for {company_name} to {user.display_name}#{user.discriminator} ({recent_positions} recent jobs, {total_positions} total)")
        
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
    loop_counter = 0
    while True:
        schedule.run_pending()  # This will respect the CHECK_INTERVAL_MINUTES setting
        
        # Every 60 seconds, log queue health status
        if loop_counter % 60 == 0:
            stats = reaction_queue.get_stats()
            processor_status = "RUNNING" if reaction_queue.is_running else "STOPPED"
            task_status = "ACTIVE" if reaction_queue.processor_task and not reaction_queue.processor_task.done() else "INACTIVE"
            
            current_queue_size = stats['current_queue_size']
            if current_queue_size > 0:
                logger.warning(f"🚨 Reaction queue health check: {current_queue_size} pending reactions "
                             f"(Total queued: {stats['total_queued']}, Processed: {stats['processed']}) "
                             f"Processor: {processor_status}, Task: {task_status}")
            else:
                logger.debug(f"✅ Reaction queue healthy: {stats['processed']} processed, {stats['total_queued']} total queued "
                           f"Processor: {processor_status}, Task: {task_status}")
        
        loop_counter += 1
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
    logger.info(f"Reaction queue stats - Queue size: {stats['current_queue_size']}, "
               f"Total queued: {stats['total_queued']}, Processed: {stats['processed']}, "
               f"Failed: {stats['failed']}, Retried: {stats['retried']}")
    
    # Try to close any remaining HTTP sessions
    try:
        if hasattr(bot, 'http') and hasattr(bot.http, 'session'):
            if not bot.http.session.closed:
                await bot.http.session.close()
                logger.debug("Discord HTTP session closed")
    except Exception as e:
        logger.debug(f"Note: HTTP session cleanup issue (non-critical): {e}")


@bot.event
async def on_resumed() -> None:
    """
    Event handler for when the bot resumes connection after disconnect.
    This is critical for restarting the reaction queue processor.
    """
    logger.info("🔄 Bot connection resumed - checking reaction queue state")
    
    # Get current queue stats
    stats = reaction_queue.get_stats()
    logger.info(f"📊 Pre-resume queue stats - Queue size: {stats['current_queue_size']}, "
               f"Total queued: {stats['total_queued']}, Processed: {stats['processed']}, "
               f"Running: {reaction_queue.is_running}")
    
    # Force restart the reaction queue processor after reconnection
    if reaction_queue.is_running:
        logger.warning("⚠️ Queue processor still marked as running, stopping first")
        await reaction_queue.stop()
    
    await reaction_queue.start()
    
    logger.info("✅ Reaction queue processor restarted successfully")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    """
    Event handler for raw reaction add events (works for uncached messages).
    This handles reactions to messages that may not be in the bot's cache.
    
    Args:
        payload: The raw reaction event payload
    """
    logger.debug(f"🎯 on_raw_reaction_add triggered! User: {payload.user_id}, Emoji: {payload.emoji}, Message: {payload.message_id}")
    
    # Skip if reactions are disabled
    if not config.enable_reactions:
        logger.debug(f"❌ Reactions disabled in config")
        return
        
    # Ignore bot's own reactions - enhanced check with detailed logging
    if payload.user_id == bot.user.id:
        logger.debug(f"❌ Ignoring bot's own reaction (User ID: {payload.user_id}, Bot ID: {bot.user.id})")
        return
    
    # Additional safety check - ignore if bot.user is not initialized
    if not bot.user:
        logger.warning(f"❌ Bot user not initialized, skipping reaction processing")
        return
    
    # Section 5.1: Selective processing - only respond to ❓ reactions
    if str(payload.emoji) != '❓':
        logger.debug(f"❌ Ignoring non-❓ reaction {payload.emoji}")
        return
    
    # Get the channel and message
    channel = bot.get_channel(payload.channel_id)
    if not channel:
        logger.warning(f"Could not find channel {payload.channel_id}")
        return
    
    try:
        message = await channel.fetch_message(payload.message_id)
    except discord.NotFound:
        logger.warning(f"Could not find message {payload.message_id}")
        return
    except discord.Forbidden:
        logger.warning(f"No permission to fetch message {payload.message_id}")
        return
    
    logger.debug(f"🔍 Message author: {message.author.id}, Bot ID: {bot.user.id}")
    
    # Check if this is a bot message (we only process reactions to our own messages)
    if message.author.id != bot.user.id:
        logger.debug(f"❌ Ignoring reaction to non-bot message")
        return
    
    # Get the user who reacted
    guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
    user = None
    
    # Try multiple ways to get the user
    if guild:
        user = guild.get_member(payload.user_id)
        logger.debug(f"🔍 Guild member lookup: {user is not None}")
    
    if not user:
        user = bot.get_user(payload.user_id)
        logger.debug(f"🔍 Bot user lookup: {user is not None}")
    
    if not user:
        # Try fetching the user from Discord API
        try:
            user = await bot.fetch_user(payload.user_id)
            logger.debug(f"🔍 Fetch user lookup: {user is not None}")
        except discord.NotFound:
            logger.warning(f"User {payload.user_id} not found via API")
        except discord.Forbidden:
            logger.warning(f"No permission to fetch user {payload.user_id}")
        except Exception as e:
            logger.warning(f"Error fetching user {payload.user_id}: {e}")
    
    if not user:
        logger.warning(f"Could not find user {payload.user_id} via any method")
        return
    
    logger.info(f"✅ Processing ❓ reaction from {user.display_name} on message {message.id}")
    
    # Get role data by message ID
    role_data = await get_role_data_by_message_id(str(message.id))
    logger.debug(f"🔍 Role data found: {role_data is not None}")
    
    if role_data:
        # Section 5.2: Send enhanced company info instead of individual job info
        logger.info(f"📨 Sending enhanced company info DM to {user.display_name}")
        await send_enhanced_company_info_dm(user, role_data)
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
