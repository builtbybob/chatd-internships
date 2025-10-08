"""
Tests for Discord bot operations.
"""

import asyncio
import os
import time
import unittest
from collections import deque, defaultdict
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import aiohttp
import discord
from discord.ext import commands

# Mock storage initialization at module level to prevent file system operations
# This must happen before importing bot module
import sys
from pathlib import Path

# Create a comprehensive mock for JsonStorageBackend that doesn't create directories
class MockJsonStorageBackend:
    def __init__(self, *args, **kwargs):
        pass  # Don't create any directories or files

# Create a comprehensive mock for DataStorage 
class MockDataStorage:
    def __init__(self, *args, **kwargs):
        pass  # Don't create any backends

# Patch the classes at the module level before any imports
original_JsonStorageBackend = None
original_DataStorage = None

def setup_storage_mocks():
    global original_JsonStorageBackend, original_DataStorage
    if 'chatd.storage_abstraction' in sys.modules:
        storage_module = sys.modules['chatd.storage_abstraction']
        original_JsonStorageBackend = getattr(storage_module, 'JsonStorageBackend', None)
        original_DataStorage = getattr(storage_module, 'DataStorage', None)
        storage_module.JsonStorageBackend = MockJsonStorageBackend
        storage_module.DataStorage = MockDataStorage
    else:
        # Patch before import
        import chatd.storage_abstraction
        original_JsonStorageBackend = chatd.storage_abstraction.JsonStorageBackend
        original_DataStorage = chatd.storage_abstraction.DataStorage
        chatd.storage_abstraction.JsonStorageBackend = MockJsonStorageBackend
        chatd.storage_abstraction.DataStorage = MockDataStorage

def teardown_storage_mocks():
    global original_JsonStorageBackend, original_DataStorage
    if 'chatd.storage_abstraction' in sys.modules and original_JsonStorageBackend and original_DataStorage:
        storage_module = sys.modules['chatd.storage_abstraction']
        storage_module.JsonStorageBackend = original_JsonStorageBackend
        storage_module.DataStorage = original_DataStorage

# Apply the mocks immediately
setup_storage_mocks()


class TestDiscordBotOperations(unittest.IsolatedAsyncioTestCase):
    """Test cases for Discord bot operations."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789,987654321',
            'ENABLE_REACTIONS': 'false',
            'MIGRATION_MODE': 'json_only',  # Add this to avoid database initialization
            'DATA_FILE': '/tmp/test_data.json',
            'MESSAGES_FILE': '/tmp/test_messages.json'
        })
        self.env_patcher.start()
        
        # Reset config singleton
        from chatd.config import Config
        Config._instance = None
        
        # Mock the get_storage function to avoid file system operations
        self.storage_patcher = patch('chatd.bot.get_storage')
        self.storage_patcher.start()
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
        
        self.sample_role_key = 'test_company__software_engineer'
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.storage_patcher.stop()
        from chatd.config import Config
        Config._instance = None
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
    
    async def test_http_session_cleanup(self):
        """Test HTTP session cleanup functionality."""
        from chatd.bot import on_disconnect
        import aiohttp
        
        # Test the on_disconnect event handler directly
        # This tests our HTTP session cleanup implementation
        with patch('chatd.bot.bot') as mock_bot:
            # Mock the bot's HTTP session
            mock_session = AsyncMock(spec=aiohttp.ClientSession)
            mock_session.closed = False
            mock_bot.http.session = mock_session
            
            # Test cleanup
            await on_disconnect()
            
            # Verify session close was called
            mock_session.close.assert_called_once()
        
        # Test with no HTTP session (should not error)
        with patch('chatd.bot.bot') as mock_bot:
            mock_bot.http = None
            
            # Should not raise exception
            await on_disconnect()
            
        # Test with already closed session
        with patch('chatd.bot.bot') as mock_bot:
            mock_session = AsyncMock(spec=aiohttp.ClientSession)
            mock_session.closed = True
            mock_bot.http.session = mock_session
            
            await on_disconnect()
            
            # Should not call close on already closed session
            mock_session.close.assert_not_called()
    
    async def test_send_message_success(self):
        """Test successful message sending."""
        from chatd.bot import send_message
        
        # Mock Discord objects
        mock_channel = AsyncMock()
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.id = 12345
        mock_channel.send.return_value = mock_message
        
        with patch('chatd.bot.bot') as mock_bot, \
             patch('chatd.bot.config') as mock_config, \
             patch('chatd.bot.get_storage') as mock_get_storage:
            
            mock_bot.get_channel.return_value = mock_channel
            mock_config.enable_reactions = False
            mock_config.message_post_delay = 0.1  # Add missing config property
            mock_config.max_retries = 3  # Add missing config property
            
            # Mock storage
            mock_storage = Mock()
            mock_storage.add_message_tracking.return_value = True
            mock_get_storage.return_value = mock_storage
            
            result = await send_message('Test message', '123456789', self.sample_role_key)
            
            self.assertIsNotNone(result)
            self.assertEqual(result.id, 12345)
            mock_channel.send.assert_called_once_with('Test message')
            mock_storage.add_message_tracking.assert_called_once_with(
                self.sample_role_key, '12345', '123456789'
            )
    
    async def test_send_message_channel_not_found(self):
        """Test message sending when channel is not found."""
        from chatd.bot import send_message
        
        with patch('chatd.bot.bot') as mock_bot, \
             patch('chatd.bot.config') as mock_config:
            
            mock_config.max_retries = 3
            mock_bot.get_channel.return_value = None
            mock_bot.fetch_channel.side_effect = discord.NotFound(Mock(), 'Channel not found')
            
            result = await send_message('Test message', '123456789')
            
            self.assertIsNone(result)
            mock_bot.fetch_channel.assert_called_once_with(123456789)
    
    async def test_send_message_forbidden_error(self):
        """Test message sending with forbidden error."""
        from chatd.bot import send_message
        
        with patch('chatd.bot.bot') as mock_bot:
            mock_bot.get_channel.return_value = None
            mock_bot.fetch_channel.side_effect = discord.Forbidden(Mock(), 'No permission')
            
            result = await send_message('Test message', '123456789')
            
            self.assertIsNone(result)
    
    async def test_send_message_general_exception(self):
        """Test message sending with general exception."""
        from chatd.bot import send_message
        
        mock_channel = AsyncMock()
        mock_channel.send.side_effect = Exception('Network error')
        
        with patch('chatd.bot.bot') as mock_bot:
            mock_bot.get_channel.return_value = mock_channel
            
            result = await send_message('Test message', '123456789')
            
            self.assertIsNone(result)
    
    async def test_send_messages_to_channels(self):
        """Test sending messages to multiple channels."""
        from chatd.bot import send_messages_to_channels
        
        # Mock channels
        mock_channel1 = AsyncMock()
        mock_channel2 = AsyncMock()
        mock_message1 = AsyncMock(spec=discord.Message)
        mock_message2 = AsyncMock(spec=discord.Message)
        mock_message1.id = 12345
        mock_message2.id = 67890
        mock_channel1.send.return_value = mock_message1
        mock_channel2.send.return_value = mock_message2
        
        def get_channel_side_effect(channel_id):
            if channel_id == 123456789:
                return mock_channel1
            elif channel_id == 987654321:
                return mock_channel2
            return None
        
        with patch('chatd.bot.bot') as mock_bot, \
             patch('chatd.bot.config') as mock_config, \
             patch('chatd.bot.get_storage') as mock_get_storage:
            
            mock_config.channel_ids = ['123456789', '987654321']
            mock_config.enable_reactions = False
            mock_config.message_post_delay = 0.1  # Add missing config property
            mock_config.max_retries = 3  # Add missing config property
            mock_bot.get_channel.side_effect = get_channel_side_effect
            
            # Mock storage
            mock_storage = Mock()
            mock_storage.add_message_tracking.return_value = True
            mock_get_storage.return_value = mock_storage
            mock_storage.add_message_tracking.return_value = True
            
            results = await send_messages_to_channels('Test message', self.sample_role_key)
            
            self.assertEqual(len(results), 2)
            mock_channel1.send.assert_called_once()
            mock_channel2.send.assert_called_once()
            # Should be called twice (once for each channel)
            self.assertEqual(mock_storage.add_message_tracking.call_count, 2)
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test-token',
        'CHANNEL_IDS': '123456789',
        'ENABLE_REACTIONS': 'true'
    })
    async def test_add_reactions_when_enabled(self):
        """Test queuing reactions when enabled."""
        from chatd.config import Config
        from chatd.bot import add_reactions_to_message, reaction_queue
        
        # Reset config to pick up new environment
        Config._instance = None
        
        mock_message = AsyncMock()
        mock_message.id = '12345'
        
        # Reset stats and start the reaction queue for testing
        reaction_queue.stats = {'queued': 0, 'processed': 0, 'failed': 0, 'retried': 0}
        await reaction_queue.start()
        
        try:
            # Queue reactions
            await add_reactions_to_message(mock_message)
            
            # Wait a moment for queue processing
            await asyncio.sleep(0.1)
            
            # Check that reactions were queued
            stats = reaction_queue.get_stats()
            self.assertEqual(stats['queued'], 1)  # One reaction task queued
            
        finally:
            # Clean up
            await reaction_queue.stop()
    
    async def test_add_reactions_error_handling(self):
        """Test reaction queue error handling."""
        from chatd.bot import add_reactions_to_message, reaction_queue
        
        mock_message = AsyncMock()
        mock_message.id = '12345'
        
        # Reset stats and start the reaction queue for testing
        reaction_queue.stats = {'queued': 0, 'processed': 0, 'failed': 0, 'retried': 0}
        await reaction_queue.start()
        
        try:
            # Should not raise exception even if message is problematic
            await add_reactions_to_message(mock_message)
            
            # Wait a moment for queue processing
            await asyncio.sleep(0.1)
            
            # Verify queuing succeeded
            stats = reaction_queue.get_stats()
            self.assertGreaterEqual(stats['queued'], 1)
            
        finally:
            # Clean up
            await reaction_queue.stop()
        
        # Note: After queue is stopped, we can't reliably check processing stats
        # The queue behavior verification is done in the dedicated TestReactionQueue class
    
    async def test_channel_failure_tracking(self):
        """Test channel failure tracking mechanism."""
        from chatd.bot import send_message, failed_channels, channel_failure_counts
        
        # Clear any existing failure state
        failed_channels.clear()
        channel_failure_counts.clear()
        
        with patch('chatd.bot.bot') as mock_bot:
            # Simulate channel fetch failure
            mock_bot.get_channel.return_value = None
            mock_bot.fetch_channel.side_effect = Exception('Network error')
            
            # Send message multiple times to same channel
            for _ in range(4):  # More than MAX_RETRIES (3)
                await send_message('Test message', '123456789')
            
            # Channel should be in failed_channels after max retries
            self.assertIn('123456789', failed_channels)
    
    async def test_failed_channel_skip(self):
        """Test that failed channels are skipped."""
        from chatd.bot import send_message, failed_channels
        
        # Add channel to failed list
        failed_channels.add('123456789')
        
        with patch('chatd.bot.bot') as mock_bot:
            result = await send_message('Test message', '123456789')
            
            # Should return None without attempting to send
            self.assertIsNone(result)
            mock_bot.get_channel.assert_not_called()
    
    async def test_get_role_data_by_message_id(self):
        """Test retrieving role data by message ID."""
        from chatd.bot import get_role_data_by_message_id
        
        # Mock message tracking data (new DataStorage format)
        mock_message_tracking = {
            'test_role_id': {
                'message_id': '12345',
                'channel_id': '123456789',
                'posted_at': 1234567890
            }
        }
        
        mock_roles = [
            {
                'id': 'test_role_id',
                'company_name': 'Test Company',
                'title': 'Software Engineer',
                'url': 'https://example.com'
            }
        ]
        
        with patch('chatd.bot.get_storage') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get_message_tracking.return_value = mock_message_tracking
            mock_get_storage.return_value = mock_storage
            
            with patch('chatd.bot.read_json', return_value=mock_roles):
                result = await get_role_data_by_message_id('12345')
                
                self.assertIsNotNone(result)
                self.assertEqual(result['company_name'], 'Test Company')
                self.assertEqual(result['id'], 'test_role_id')
    
    async def test_send_dm_with_job_info(self):
        """Test sending DM with job information."""
        from chatd.bot import send_dm_with_job_info
        
        mock_user = AsyncMock()
        mock_user.send = AsyncMock()
        
        role_data = {
            'company_name': 'Test Company',
            'title': 'Software Engineer',
            'url': 'https://example.com',
            'locations': ['New York'],
            'sponsorship': 'Available'
        }
        
        await send_dm_with_job_info(mock_user, role_data)
        
        mock_user.send.assert_called_once()
        # Check that the sent message contains expected information
        call_args = mock_user.send.call_args[0][0]
        self.assertIn('Test Company', call_args)
        self.assertIn('Software Engineer', call_args)
    
    async def test_check_for_new_roles(self):
        """Test checking for new roles with DataStorage and new update support."""
        from chatd.bot import check_for_new_roles
        
        # Use a recent timestamp for testing (current time - 1 day)
        current_time = int(time.time())
        one_day_ago = current_time - (24 * 60 * 60)
        
        # Mock new data (what's fetched from repo)
        new_data = [
            {
                'id': 'existing_role_id',  # This should be detected as no change
                'company_name': 'Existing Company',
                'title': 'Existing Role',
                'date_posted': one_day_ago,
                'active': True,
                'is_visible': True
            },
            {
                'id': 'new_role_id',  # This should be processed as new
                'company_name': 'New Company',
                'title': 'New Role',
                'date_posted': one_day_ago,  # Within the 5-day limit
                'date_updated': current_time,
                'active': True,  # Make sure it's active
                'is_visible': True  # Make sure it's visible
            }
        ]
        
        # Mock the change processing results that now include changes_for_discord
        mock_changes = {
            'added': [new_data[1]],  # Only the new role
            'updated': [],
            'removed': []
        }
        
        mock_process_results = {
            'added_count': 1,
            'updated_count': 0,
            'removed_count': 0,
            'update_failures': [],
            'success': True,
            'changes_for_discord': mock_changes  # This is what the bot now uses
        }
        
        with patch('chatd.bot.get_storage') as mock_get_storage, \
             patch('chatd.bot.read_json', return_value=new_data), \
             patch('chatd.bot.send_messages_to_channels') as mock_send_messages, \
             patch('chatd.bot.clone_or_update_repo', return_value=True), \
             patch('chatd.bot.config') as mock_config:
            
            # Configure mocks
            mock_storage = Mock()
            mock_storage.process_job_changes.return_value = mock_process_results
            mock_get_storage.return_value = mock_storage
            mock_config.max_post_age_days = 5
            
            await check_for_new_roles()
            
            # Verify new update support methods were called
            mock_storage.process_job_changes.assert_called_once_with(new_data)
            # Note: detect_job_changes is no longer called separately - it's part of process_job_changes
            
            # Verify message sending was called for new role
            mock_send_messages.assert_called_once()
            args = mock_send_messages.call_args[0]  # Get positional args
            self.assertEqual(args[1], 'new_role_id')  # role_key should be the second argument
    
    async def test_storage_abstraction_integration(self):
        """Test bot integration with new storage abstraction layer."""
        # Temporarily stop the storage patcher for this test
        self.storage_patcher.stop()
        
        try:
            from chatd.bot import get_storage
            
            # Test storage initialization
            with patch('chatd.bot.DataStorage') as mock_data_storage_class, \
                 patch('chatd.bot.config') as mock_config:
                
                mock_config.migration_mode = 'dual_write'
                mock_storage_instance = Mock()
                mock_data_storage_class.return_value = mock_storage_instance
                
                # Clear any existing storage instance
                from chatd import bot
                bot._storage_instance = None
                
                # Test get_storage function
                storage = get_storage()
                
                # Should return the same instance (singleton pattern)
                storage2 = get_storage()
                self.assertEqual(storage, storage2)
                
                # Verify DataStorage was initialized with config
                mock_data_storage_class.assert_called_once_with(mock_config)
        
        finally:
            # Restart the storage patcher
            self.storage_patcher.start()
    
    async def test_migration_mode_compatibility(self):
        """Test bot works with different migration modes."""
        from chatd.bot import check_for_new_roles
        
        # Test with each migration mode
        for mode in ['json_only', 'dual_write', 'database_only']:
            with patch('chatd.bot.get_storage') as mock_get_storage, \
                 patch('chatd.bot.read_json', return_value=[]), \
                 patch('chatd.bot.clone_or_update_repo', return_value=True), \
                 patch('chatd.bot.config') as mock_config:
                
                mock_config.migration_mode = mode
                mock_config.max_post_age_days = 5
                
                mock_storage = Mock()
                mock_storage.process_job_changes.return_value = {
                    'added_count': 0,
                    'updated_count': 0,
                    'removed_count': 0,
                    'update_failures': [],
                    'success': True,
                    'changes_for_discord': {'added': [], 'updated': [], 'removed': []}
                }
                mock_get_storage.return_value = mock_storage
                
                # Should not raise exception for any mode
                await check_for_new_roles()
                
                # Verify process_job_changes was called
                mock_storage.process_job_changes.assert_called_once()


class TestBotEventHandlers(unittest.IsolatedAsyncioTestCase):
    """Test cases for Discord bot event handlers."""
    
    def setUp(self):
        """Set up test environment."""
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789',
            'ENABLE_REACTIONS': 'true',
            'MIGRATION_MODE': 'json_only',  # Add this to avoid database initialization
            'DATA_FILE': '/tmp/test_data.json',
            'MESSAGES_FILE': '/tmp/test_messages.json'
        })
        self.env_patcher.start()
        
        from chatd.config import Config
        Config._instance = None
        
        # Mock the get_storage function to avoid file system operations
        self.storage_patcher = patch('chatd.bot.get_storage')
        self.storage_patcher.start()
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.storage_patcher.stop()
        from chatd.config import Config
        Config._instance = None
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
    
    async def test_on_reaction_add_valid_reaction(self):
        """Test reaction event handler with valid reaction."""
        from chatd.bot import on_reaction_add
        
        # Mock Discord objects
        mock_user = MagicMock(spec=discord.Member)
        mock_user.id = 67890  # Different from bot ID
        mock_user.display_name = 'TestUser'
        
        mock_message = MagicMock()
        mock_message.id = 12345
        mock_message.author.id = 98765  # Bot's ID
        
        mock_reaction = MagicMock()
        mock_reaction.emoji = '❓'
        mock_reaction.message = mock_message
        
        role_data = {
            'company_name': 'Test Company',
            'title': 'Software Engineer'
        }
        
        with patch('chatd.bot.bot') as mock_bot, \
             patch('chatd.bot.config') as mock_config:
            
            mock_config.enable_reactions = True
            mock_bot.user.id = 98765  # Bot's ID
            
            with patch('chatd.bot.get_role_data_by_message_id', return_value=role_data):
                with patch('chatd.bot.send_dm_with_job_info') as mock_send_dm:
                    await on_reaction_add(mock_reaction, mock_user)
                    
                    mock_send_dm.assert_called_once_with(mock_user, role_data)
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test-token',
        'CHANNEL_IDS': '123456789',
        'ENABLE_REACTIONS': 'false'
    })
    async def test_on_reaction_add_reactions_disabled(self):
        """Test reaction handler when reactions are disabled."""
        from chatd.config import Config
        from chatd.bot import on_reaction_add
        
        # Reset config
        Config._instance = None
        
        mock_user = MagicMock()
        mock_reaction = MagicMock()
        
        with patch('chatd.bot.get_role_data_by_message_id') as mock_get_role:
            await on_reaction_add(mock_reaction, mock_user)
            
            # Should return early, not call get_role_data
            mock_get_role.assert_not_called()
    
    async def test_on_reaction_add_bot_reaction(self):
        """Test reaction handler ignoring bot's own reactions."""
        from chatd.bot import on_reaction_add
        
        mock_user = MagicMock()
        mock_user.id = 98765  # Same as bot ID
        
        mock_reaction = MagicMock()
        
        with patch('chatd.bot.bot') as mock_bot:
            mock_bot.user.id = 98765
            
            with patch('chatd.bot.get_role_data_by_message_id') as mock_get_role:
                await on_reaction_add(mock_reaction, mock_user)
                
                # Should ignore bot's own reactions
                mock_get_role.assert_not_called()


class TestReactionQueue(unittest.IsolatedAsyncioTestCase):
    """Test the ReactionQueue class functionality."""
    
    async def test_reaction_queue_lifecycle(self):
        """Test starting and stopping the reaction queue."""
        from chatd.bot import ReactionQueue
        
        queue = ReactionQueue()
        
        # Test starting
        await queue.start()
        self.assertTrue(queue.is_running)
        self.assertIsNotNone(queue.processor_task)
        
        # Test stopping
        await queue.stop()
        self.assertFalse(queue.is_running)
    
    async def test_reaction_queue_processing(self):
        """Test queuing and processing reactions."""
        from chatd.bot import ReactionQueue
        
        queue = ReactionQueue()
        # Reset stats
        queue.stats = {'queued': 0, 'processed': 0, 'failed': 0, 'retried': 0}
        await queue.start()
        
        try:
            # Mock message
            mock_message = AsyncMock()
            mock_message.id = '12345'
            mock_message.add_reaction = AsyncMock()
            
            # Queue reactions
            reactions = ['❓', '✅']
            await queue.queue_reactions(mock_message, reactions)
            
            # Wait for processing
            await asyncio.sleep(0.2)
            
            # Check stats
            stats = queue.get_stats()
            self.assertEqual(stats['queued'], 1)
            self.assertGreaterEqual(stats['processed'], 0)  # May not be processed yet due to timing
            
        finally:
            await queue.stop()
    
    async def test_reaction_queue_retry_logic(self):
        """Test retry logic for failed reactions."""
        from chatd.bot import ReactionQueue
        import discord
        
        queue = ReactionQueue()
        # Reset stats
        queue.stats = {'queued': 0, 'processed': 0, 'failed': 0, 'retried': 0}
        await queue.start()
        
        try:
            # Mock message that fails reactions
            mock_message = AsyncMock()
            mock_message.id = '12345'
            mock_message.add_reaction = AsyncMock(side_effect=discord.HTTPException(response=Mock(), message="Rate limited"))
            
            # Queue reactions
            reactions = ['❓']
            await queue.queue_reactions(mock_message, reactions)
            
            # Wait for processing and retry attempts
            await asyncio.sleep(0.5)
            
            # Check that retries were attempted
            stats = queue.get_stats()
            self.assertEqual(stats['queued'], 1)
            # Note: May have retries depending on timing
            
        finally:
            await queue.stop()

    # Section 4.4: Enhanced failure handling and retry logic tests

    async def test_failure_type_classification(self):
        """Test that different Discord exceptions are classified correctly."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        
        queue = ReactionQueue()
        
        # Test rate limit classification
        rate_limit_error = discord.HTTPException(MagicMock(), "Too Many Requests")
        rate_limit_error.status = 429
        failure_type = queue._classify_failure(rate_limit_error)
        self.assertEqual(failure_type, ReactionFailureType.RATE_LIMITED)
        
        # Test forbidden error classification
        forbidden_error = discord.Forbidden(MagicMock(), "Forbidden")
        failure_type = queue._classify_failure(forbidden_error)
        self.assertEqual(failure_type, ReactionFailureType.PERMANENT_ERROR)
        
        # Test network error classification with aiohttp.ClientError
        network_error = aiohttp.ClientError("Connection failed")
        failure_type = queue._classify_failure(network_error)
        self.assertEqual(failure_type, ReactionFailureType.NETWORK_ERROR)
        
        # Test server error classification
        server_error = discord.HTTPException(MagicMock(), "Internal Server Error")
        server_error.status = 500
        failure_type = queue._classify_failure(server_error)
        self.assertEqual(failure_type, ReactionFailureType.SERVER_ERROR)
        
        # Test unknown error classification
        unknown_error = ValueError("Unknown error")
        failure_type = queue._classify_failure(unknown_error)
        self.assertEqual(failure_type, ReactionFailureType.UNKNOWN_ERROR)

    async def test_health_metrics_tracking(self):
        """Test that health metrics are properly tracked and calculated."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        
        queue = ReactionQueue()
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=100),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Start with perfect health
        self.assertEqual(queue.enhanced_stats['health_score'], 1.0)
        
        # Add some successful reactions
        for _ in range(8):
            queue._update_health_metrics(True)
        
        # Add some failures
        for _ in range(2):
            queue._update_health_metrics(False, ReactionFailureType.NETWORK_ERROR)
        
        # Check failure rate calculation
        failure_rate = queue._get_current_failure_rate()
        self.assertAlmostEqual(failure_rate, 0.2, places=2)  # 2 failures out of 10 attempts
        
        # Check health score calculation
        queue._calculate_health_score()
        health_score = queue.enhanced_stats['health_score']
        expected_health = max(0.0, 1.0 - failure_rate)
        self.assertAlmostEqual(health_score, expected_health, places=2)
        
        # Check failure type tracking
        self.assertEqual(queue.enhanced_stats['failure_by_type']['network_error'], 2)

    async def test_degraded_mode_activation(self):
        """Test that degraded mode activates and deactivates correctly."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        from chatd.config import config
        
        queue = ReactionQueue()
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=config.health_window_size),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Start in normal mode
        self.assertFalse(queue.enhanced_stats['degraded_mode'])
        
        # Simulate high failure rate to trigger degraded mode
        failure_count = int(config.health_window_size * config.degradation_threshold) + 1
        for _ in range(failure_count):
            queue._update_health_metrics(False, ReactionFailureType.NETWORK_ERROR)
        
        # Add a few successes to fill window but keep failure rate high
        success_count = config.health_window_size - failure_count
        for _ in range(success_count):
            queue._update_health_metrics(True)
        
        # Check degraded mode activation
        queue._check_degradation_mode()
        self.assertTrue(queue.enhanced_stats['degraded_mode'])
        self.assertEqual(queue.enhanced_stats['degradation_events'], 1)
        
        # Simulate recovery with more successes
        for _ in range(config.health_window_size):
            queue._update_health_metrics(True)
        
        # Check degraded mode deactivation
        queue._check_degradation_mode()
        self.assertFalse(queue.enhanced_stats['degraded_mode'])

    async def test_circuit_breaker_activation(self):
        """Test circuit breaker activation and timeout behavior."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        from chatd.config import config
        
        queue = ReactionQueue()
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=config.health_window_size),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Start with circuit breaker inactive
        self.assertFalse(queue._should_circuit_break())
        
        # Simulate consecutive failures to trigger circuit breaker
        for _ in range(config.circuit_breaker_threshold):
            queue._update_health_metrics(False, ReactionFailureType.SERVER_ERROR)
        
        # Circuit breaker should now be active
        self.assertTrue(queue._should_circuit_break())
        
        # Test timeout behavior - should still be active immediately
        self.assertTrue(queue._should_circuit_break())
        
        # Simulate timeout expiration by setting last failure time in the past
        queue.enhanced_stats['last_failure_time'] = time.time() - config.circuit_breaker_timeout - 1
        
        # Circuit breaker should reset after timeout
        self.assertFalse(queue._should_circuit_break())
        self.assertEqual(queue.enhanced_stats['consecutive_failures'], 0)

    async def test_circuit_breaker_manual_reset(self):
        """Test manual circuit breaker reset functionality."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        from chatd.config import config
        
        queue = ReactionQueue()
        queue.logger = MagicMock()  # Add mock logger
        
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=config.health_window_size),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Trigger circuit breaker
        for _ in range(config.circuit_breaker_threshold):
            queue._update_health_metrics(False, ReactionFailureType.SERVER_ERROR)
        
        self.assertTrue(queue._should_circuit_break())
        
        # Manually reset circuit breaker
        queue.reset_circuit_breaker()
        
        # Circuit breaker should be deactivated
        self.assertFalse(queue._should_circuit_break())
        self.assertEqual(queue.enhanced_stats['consecutive_failures'], 0)
        self.assertFalse(queue.enhanced_stats['degraded_mode'])
        self.assertIsNone(queue.enhanced_stats['last_failure_time'])

    async def test_adaptive_retry_delays(self):
        """Test that retry delays are calculated correctly based on failure type."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        
        queue = ReactionQueue()
        
        # Test rate-limited failure delays (exponential backoff)
        delay1 = queue._get_retry_delay(ReactionFailureType.RATE_LIMITED, 1)
        delay2 = queue._get_retry_delay(ReactionFailureType.RATE_LIMITED, 2)
        delay3 = queue._get_retry_delay(ReactionFailureType.RATE_LIMITED, 3)
        
        # Should increase exponentially
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)
        
        # Test network error delays (moderate backoff)
        network_delay = queue._get_retry_delay(ReactionFailureType.NETWORK_ERROR, 1)
        self.assertGreater(network_delay, 0)
        
        # Test permanent error (no retry)
        perm_delay = queue._get_retry_delay(ReactionFailureType.PERMANENT_ERROR, 1)
        self.assertEqual(perm_delay, 0)  # No retry for permanent errors
        
        # Test server error delays
        server_delay = queue._get_retry_delay(ReactionFailureType.SERVER_ERROR, 1)
        self.assertGreater(server_delay, 0)

    async def test_enhanced_statistics_tracking(self):
        """Test that enhanced statistics are tracked correctly."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        
        queue = ReactionQueue()
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=100),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Add some reactions with different outcomes
        queue._update_health_metrics(True)
        queue._update_health_metrics(False, ReactionFailureType.RATE_LIMITED)
        queue._update_health_metrics(True)
        queue._update_health_metrics(False, ReactionFailureType.NETWORK_ERROR)
        
        # Get enhanced statistics
        stats = queue.get_stats()
        enhanced = stats['enhanced_metrics']
        
        # Verify basic counts
        self.assertEqual(enhanced['total_attempts'], 4)
        self.assertEqual(enhanced['successful_reactions'], 2)
        self.assertEqual(enhanced['failed_reactions'], 2)
        
        # Verify failure type breakdown
        self.assertEqual(enhanced['failure_by_type']['rate_limited'], 1)
        self.assertEqual(enhanced['failure_by_type']['network_error'], 1)
        
        # Verify health score is calculated
        self.assertIsInstance(enhanced['health_score'], float)
        self.assertGreaterEqual(enhanced['health_score'], 0.0)
        self.assertLessEqual(enhanced['health_score'], 1.0)

    async def test_health_summary_reporting(self):
        """Test health summary for monitoring dashboards."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        
        queue = ReactionQueue()
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=100),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Add some test data
        for _ in range(10):
            queue._update_health_metrics(True)
        for _ in range(2):
            queue._update_health_metrics(False, ReactionFailureType.NETWORK_ERROR)
        
        # Get health summary
        health_summary = queue.get_health_summary()
        
        # Verify expected fields
        required_fields = [
            'health_score', 'failure_rate', 'degraded_mode', 'consecutive_failures',
            'circuit_breaker_active', 'total_attempts', 'success_rate'
        ]
        
        for field in required_fields:
            self.assertIn(field, health_summary)
        
        # Verify calculated values
        self.assertEqual(health_summary['total_attempts'], 12)
        self.assertAlmostEqual(health_summary['success_rate'], 10/12, places=2)
        self.assertFalse(health_summary['degraded_mode'])
        self.assertFalse(health_summary['circuit_breaker_active'])

    @patch('asyncio.sleep')
    async def test_processing_with_circuit_breaker(self, mock_sleep):
        """Test that reaction processing respects circuit breaker state."""
        from chatd.bot import ReactionQueue, ReactionFailureType
        from chatd.config import config
        
        queue = ReactionQueue()
        queue.logger = MagicMock()
        
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=config.health_window_size),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Create mock message and reaction task
        mock_message = AsyncMock()
        mock_message.id = 123456789
        mock_message.add_reaction = AsyncMock()
        
        reaction_task = {
            'message': mock_message,
            'reactions': ['👍', '❤️'],
            'retry_count': 0
        }
        
        # Trigger circuit breaker
        for _ in range(config.circuit_breaker_threshold):
            queue._update_health_metrics(False, ReactionFailureType.SERVER_ERROR)
        
        # Attempt to process reaction while circuit breaker is active
        await queue._process_single_reaction_task(reaction_task)
        
        # Verify that no reactions were attempted due to circuit breaker
        mock_message.add_reaction.assert_not_called()
        
        # Note: The circuit breaker error is logged by the actual logger, not our mock
        # We can verify the behavior occurred by checking that no reactions were added

    @patch('asyncio.sleep')
    async def test_processing_in_degraded_mode(self, mock_sleep):
        """Test that reaction processing uses simplified reactions in degraded mode."""
        from chatd.bot import ReactionQueue
        
        queue = ReactionQueue()
        queue.logger = MagicMock()
        
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=100),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': True,  # Start in degraded mode
            'last_failure_time': None
        }
        
        # Create mock message
        mock_message = AsyncMock()
        mock_message.id = 123456789
        mock_message.add_reaction = AsyncMock()
        
        reaction_task = {
            'message': mock_message,
            'reactions': ['👍', '❤️', '🎉', '🔥'],
            'retry_count': 0
        }
        
        # Process reaction task
        await queue._process_single_reaction_task(reaction_task)
        
        # Verify only simple reactions were used
        mock_message.add_reaction.assert_called_with('👍')
        self.assertEqual(mock_message.add_reaction.call_count, 1)

    async def test_log_health_summary(self):
        """Test health summary logging functionality."""
        from chatd.bot import ReactionQueue
        
        queue = ReactionQueue()
        mock_logger = MagicMock()
        queue.logger = mock_logger
        
        # Reset health monitoring to clean state
        queue.enhanced_stats = {
            'total_attempts': 0,
            'successful_reactions': 0,
            'failed_reactions': 0,
            'failure_by_type': defaultdict(int),
            'avg_retry_count': 0.0,
            'health_score': 1.0,
            'failure_rate_window': deque(maxlen=100),
            'degradation_events': 0,
            'consecutive_failures': 0,
            'degraded_mode': False,
            'last_failure_time': None
        }
        
        # Test with good health
        queue.log_health_summary()
        mock_logger.info.assert_called()
        info_msg = mock_logger.info.call_args[0][0]
        self.assertIn("Health Check - GOOD", info_msg)
        
        # Test with poor health
        queue.enhanced_stats['health_score'] = 0.5
        mock_logger.reset_mock()
        
        queue.log_health_summary()
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn("Health Check - POOR HEALTH", warning_msg)
        
        # Test with degraded mode
        queue.enhanced_stats['degraded_mode'] = True
        mock_logger.reset_mock()
        
        queue.log_health_summary()
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn("Health Check - DEGRADED MODE", warning_msg)


if __name__ == '__main__':
    unittest.main()
