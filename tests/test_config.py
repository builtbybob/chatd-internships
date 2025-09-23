"""
Tests for the configuration module.
"""

import os
import unittest
from unittest.mock import patch

from chatd.config import Config, validate_config


class TestConfig(unittest.TestCase):
    """Test cases for the Config class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Clear the singleton instance
        Config._instance = None
        
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789,987654321',
            'LOG_LEVEL': 'DEBUG',
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up after the test."""
        self.env_patcher.stop()
    
    def test_singleton(self):
        """Test that Config is a singleton."""
        config1 = Config()
        config2 = Config()
        self.assertIs(config1, config2)
    
    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {'LOCAL_REPO_PATH': '/tmp/test-repo'}, clear=False):
            # Reset the Config singleton to pick up the patched environment variable
            Config._instance = None
            config = Config()
            self.assertEqual(config.repo_url, 'https://github.com/SimplifyJobs/Summer2026-Internships.git')
            self.assertEqual(config.local_repo_path, '/tmp/test-repo')  # Now matches the mocked environment variable
            self.assertEqual(config.max_retries, 3)
            self.assertEqual(config.check_interval_minutes, 1)
            self.assertEqual(config.enable_reactions, False)  # Test default reaction setting
    
    def test_environment_values(self):
        """Test environment variable configuration values."""
        config = Config()
        self.assertEqual(config.discord_token, 'test-token')
        self.assertEqual(config.channel_ids, ['123456789', '987654321'])
        self.assertEqual(config.log_level, 'DEBUG')
    
    @patch('sys.exit')
    @patch('chatd.config.Config._validate_discord_connection', return_value=True)
    @patch('chatd.config.Config._validate_repository', return_value=True)
    @patch('chatd.config.Config._validate_file_permissions', return_value=True)
    @patch('chatd.config.Config._validate_numeric_config', return_value=True)
    @patch('chatd.config.Config._validate_channel_ids', return_value=True)
    @patch('chatd.config.Config._validate_discord_token', return_value=True)
    def test_validate_config(self, mock_token, mock_channels, mock_numeric, mock_files, mock_repo, mock_discord, mock_exit):
        """Test configuration validation."""
        # Set up additional environment variables needed for testing
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token-long-enough-to-pass-validation-checks-1234567890',
            'CHANNEL_IDS': '123456789012345678,987654321098765432',
            'DATA_FILE': '/tmp/test-data/previous_data.json',
            'MESSAGES_FILE': '/tmp/test-data/message_tracking.json',
            'CURRENT_HEAD_FILE': '/tmp/test-data/current_head.txt',
            'LOG_FILE': '/tmp/test-logs/chatd.log',
            'LOCAL_REPO_PATH': '/tmp/test-repo'
        }):
            # Reset singleton to reload with new env vars
            Config._instance = None
            result = validate_config()
            # If sys.exit was called, that means validation failed
            mock_exit.assert_not_called()
            self.assertTrue(result)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_config_missing_vars(self):
        """Test configuration validation with missing variables."""
        # Reset the singleton
        Config._instance = None
        
        # This should exit, so we expect a SystemExit exception
        with self.assertRaises(SystemExit):
            validate_config()


if __name__ == '__main__':
    unittest.main()
