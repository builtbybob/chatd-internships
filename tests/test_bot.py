"""
Tests for Discord bot operations.
"""

import asyncio
import os
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import discord
from discord.ext import commands


class TestDiscordBotOperations(unittest.IsolatedAsyncioTestCase):
    """Test cases for Discord bot operations."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789,987654321',
            'ENABLE_REACTIONS': 'false'
        })
        self.env_patcher.start()
        
        # Reset config singleton
        from chatd.config import Config
        Config._instance = None
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
        
        self.sample_role_key = 'test_company__software_engineer'
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        from chatd.config import Config
        Config._instance = None
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
    
    async def test_send_message_success(self):
        """Test successful message sending."""
        from chatd.bot import send_message
        
        # Mock Discord objects
        mock_channel = AsyncMock()
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.id = 12345
        mock_channel.send.return_value = mock_message
        
        with patch('chatd.bot.bot') as mock_bot, \
             patch('chatd.bot.config') as mock_config:
            
            mock_bot.get_channel.return_value = mock_channel
            mock_config.enable_reactions = False
            
            # Mock storage
            with patch('chatd.bot.get_storage') as mock_get_storage:
                mock_storage = MagicMock()
                mock_storage.save_message_info.return_value = True
                mock_get_storage.return_value = mock_storage
                
                result = await send_message('Test message', '123456789', self.sample_role_key)
                
                self.assertIsNotNone(result)
                self.assertEqual(result.id, 12345)
                mock_channel.send.assert_called_once_with('Test message')
                mock_storage.save_message_info.assert_called_once()
    
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
             patch('chatd.bot.config') as mock_config:
            
            mock_config.channel_ids = ['123456789', '987654321']
            mock_config.enable_reactions = False
            mock_bot.get_channel.side_effect = get_channel_side_effect
            
            # Mock storage
            with patch('chatd.bot.get_storage') as mock_get_storage:
                mock_storage = MagicMock()
                mock_storage.save_message_info.return_value = True
                mock_get_storage.return_value = mock_storage
                
                results = await send_messages_to_channels('Test message', self.sample_role_key)
                
                self.assertEqual(len(results), 2)
                mock_channel1.send.assert_called_once()
                mock_channel2.send.assert_called_once()
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test-token',
        'CHANNEL_IDS': '123456789',
        'ENABLE_REACTIONS': 'true'
    })
    async def test_add_reactions_when_enabled(self):
        """Test adding reactions when enabled."""
        from chatd.config import Config
        from chatd.bot import add_reactions_to_message
        
        # Reset config to pick up new environment
        Config._instance = None
        
        mock_message = AsyncMock()
        mock_message.add_reaction = AsyncMock()
        
        await add_reactions_to_message(mock_message)
        
        # Should add both reactions
        self.assertEqual(mock_message.add_reaction.call_count, 2)
        mock_message.add_reaction.assert_any_call('❓')
        mock_message.add_reaction.assert_any_call('✅')
    
    async def test_add_reactions_error_handling(self):
        """Test reaction adding with error handling."""
        from chatd.bot import add_reactions_to_message
        
        mock_message = AsyncMock()
        mock_message.add_reaction.side_effect = Exception('Network error')
        
        # Should not raise exception
        await add_reactions_to_message(mock_message)
        
        # Should have attempted to add reactions
        self.assertGreater(mock_message.add_reaction.call_count, 0)
    
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
        
        # Mock storage with message data
        mock_messages = [
            {'message_id': '12345', 'channel_id': '123456789', 'role_key': 'test_role'}
        ]
        
        mock_roles = [
            {
                'id': 'test_role',
                'company_name': 'Test Company',
                'title': 'Software Engineer',
                'url': 'https://example.com'
            }
        ]
        
        with patch('chatd.bot.get_storage') as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.get_messages_for_role.return_value = mock_messages
            mock_get_storage.return_value = mock_storage
            
            with patch('chatd.bot.read_json', return_value=mock_roles):
                result = await get_role_data_by_message_id('12345')
                
                self.assertIsNotNone(result)
                self.assertEqual(result['company_name'], 'Test Company')
    
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


class TestBotEventHandlers(unittest.IsolatedAsyncioTestCase):
    """Test cases for Discord bot event handlers."""
    
    def setUp(self):
        """Set up test environment."""
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789',
            'ENABLE_REACTIONS': 'true'
        })
        self.env_patcher.start()
        
        from chatd.config import Config
        Config._instance = None
        
        # Clear global bot state
        from chatd import bot
        bot.failed_channels.clear()
        bot.channel_failure_counts.clear()
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
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


if __name__ == '__main__':
    unittest.main()
