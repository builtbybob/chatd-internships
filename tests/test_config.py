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
        config = Config()
        self.assertEqual(config.repo_url, 'https://github.com/SimplifyJobs/Summer2026-Internships.git')
        self.assertEqual(config.local_repo_path, 'Summer2026-Internships')
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.check_interval_minutes, 1)
        self.assertEqual(config.enable_reactions, False)  # Test default reaction setting
    
    def test_environment_values(self):
        """Test environment variable configuration values."""
        config = Config()
        self.assertEqual(config.discord_token, 'test-token')
        self.assertEqual(config.channel_ids, ['123456789', '987654321'])
        self.assertEqual(config.log_level, 'DEBUG')
    
    def test_validate_config(self):
        """Test configuration validation."""
        result = validate_config()
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
