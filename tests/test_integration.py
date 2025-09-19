"""
Integration tests for the chatd-internships bot.

These tests cover interaction between different modules and
end-to-end functionality using the new modular architecture.
"""

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, mock_open, MagicMock
from pathlib import Path

import discord
from discord.ext import commands


class TestIntegration(unittest.TestCase):
    """Integration test cases for the bot modules."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment for testing
        self.test_env = {
            'DISCORD_TOKEN': 'test_token',
            'CHANNEL_IDS': '123456789,987654321',
            'LOG_LEVEL': 'INFO',
            'ENABLE_REACTIONS': 'false'
        }
        
        # Sample role data for testing
        self.sample_role = {
            'company_name': 'Test Company',
            'title': 'Software Engineer Intern',
            'url': 'https://example.com/job',
            'locations': ['New York', 'Remote'],
            'terms': ['Summer 2026'],
            'sponsorship': 'Available',
            'date_posted': datetime.now().timestamp(),
            'active': True,
            'is_visible': True
        }
    
    def tearDown(self):
        """Clean up after tests."""
        # Reset any singletons
        from chatd.config import Config
        Config._instance = None
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test_token',
        'CHANNEL_IDS': '123456789,987654321',
        'LOG_LEVEL': 'INFO',
        'ENABLE_REACTIONS': 'false'
    })
    def test_config_integration(self):
        """Test configuration loading and validation."""
        from chatd.config import Config, validate_config
        
        config = Config()
        self.assertEqual(config.discord_token, 'test_token')
        self.assertEqual(config.channel_ids, ['123456789', '987654321'])
        self.assertEqual(config.enable_reactions, False)
        
        # Test validation
        result = validate_config()
        self.assertTrue(result)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_config_validation_failure(self):
        """Test configuration validation with missing required variables."""
        from chatd.config import Config, validate_config
        
        # Reset singleton
        Config._instance = None
        
        # This should not raise SystemExit in validate_config, 
        # but rather in Config.validate() which is called by validate_config
        with self.assertRaises(SystemExit):
            validate_config()
    
    def test_message_formatting_integration(self):
        """Test message formatting with complete role data."""
        from chatd.messages import format_message, format_epoch
        
        formatted = format_message(self.sample_role)
        
        # Check for key components
        self.assertIn('## Test Company', formatted)
        self.assertIn('## [Software Engineer Intern]', formatted)
        self.assertIn('New York | Remote', formatted)
        self.assertIn('### Sponsorship: `Available`', formatted)
        self.assertIn('Posted on:', formatted)
    
    def test_role_comparison_integration(self):
        """Test role comparison functionality."""
        from chatd.messages import compare_roles
        
        old_role = self.sample_role.copy()
        new_role = self.sample_role.copy()
        new_role['locations'] = ['San Francisco', 'Remote']
        new_role['sponsorship'] = 'Not Available'
        
        changes = compare_roles(old_role, new_role)
        self.assertEqual(len(changes), 2)
        self.assertTrue(any('locations changed' in change for change in changes))
        self.assertTrue(any('sponsorship changed' in change for change in changes))
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test_token',
        'CHANNEL_IDS': '123456789',
        'ENABLE_REACTIONS': 'false'
    })
    def test_storage_integration(self):
        """Test storage system integration."""
        from chatd.storage import get_storage
        
        storage = get_storage()
        
        # Test saving and loading data
        test_data = [self.sample_role]
        result = storage.save_data(test_data)
        self.assertTrue(result)
        
        loaded_data = storage.load_data()
        self.assertEqual(len(loaded_data), 1)
        self.assertEqual(loaded_data[0]['company_name'], 'Test Company')
    
    @patch('chatd.repo.git.Repo')
    @patch('os.path.exists')
    def test_repository_operations_integration(self, mock_exists, mock_repo_class):
        """Test repository operations integration."""
        from chatd.repo import clone_or_update_repo
        
        # Test fresh clone
        mock_exists.return_value = False
        mock_repo_instance = MagicMock()
        mock_repo_class.clone_from.return_value = mock_repo_instance
        
        result = clone_or_update_repo()
        self.assertTrue(result)
        mock_repo_class.clone_from.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open, read_data='[{"test": "data"}]')
    @patch('os.path.exists', return_value=True)
    def test_json_reading_integration(self, mock_exists, mock_file):
        """Test JSON file reading integration."""
        from chatd.repo import read_json
        
        data = read_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['test'], 'data')


class TestAsyncIntegration(unittest.IsolatedAsyncioTestCase):
    """Async integration tests for Discord bot functionality."""
    
    def setUp(self):
        """Set up async test environment."""
        self.test_env = {
            'DISCORD_TOKEN': 'test_token',
            'CHANNEL_IDS': '123456789,987654321',
            'LOG_LEVEL': 'INFO',
            'ENABLE_REACTIONS': 'false'
        }
        
        self.sample_role = {
            'company_name': 'Test Company',
            'title': 'Software Engineer Intern',
            'url': 'https://example.com/job',
            'locations': ['New York', 'Remote'],
            'terms': ['Summer 2026'],
            'sponsorship': 'Available',
            'date_posted': datetime.now().timestamp(),
            'active': True,
            'is_visible': True
        }
    
    def tearDown(self):
        """Clean up after async tests."""
        from chatd.config import Config
        Config._instance = None
    
    @patch.dict(os.environ, {
        'DISCORD_TOKEN': 'test_token',
        'CHANNEL_IDS': '123456789',
        'ENABLE_REACTIONS': 'false'
    })
    async def test_send_message_integration(self):
        """Test message sending integration."""
        from chatd.bot import send_message
        from chatd.messages import format_message
        from chatd.config import Config
        
        # Reset config to pick up new environment
        Config._instance = None
        
        # Mock Discord objects
        mock_channel = AsyncMock()
        mock_message = AsyncMock(spec=discord.Message)
        mock_message.id = 12345
        mock_channel.send.return_value = mock_message
        
        with patch('chatd.bot.bot') as mock_bot:
            mock_bot.get_channel.return_value = mock_channel
            
            # Mock storage
            with patch('chatd.bot.get_storage') as mock_get_storage:
                mock_storage = MagicMock()
                mock_storage.save_message_info.return_value = True
                mock_get_storage.return_value = mock_storage
                
                message = format_message(self.sample_role)
                result = await send_message(message, '123456789', 'test_role_key')
                
                self.assertIsNotNone(result)
                mock_channel.send.assert_called_once_with(message)


if __name__ == '__main__':
    unittest.main()
