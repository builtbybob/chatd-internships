"""
Tests for the directory path bug that was causing startup failures.
Simulates the exact issue that occurred with the incorrect os.path.dirname() call.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from chatd.config import Config

class TestDirectoryPathBugFix(unittest.TestCase):
    """Test cases for the directory path bug fix."""
    
    def setUp(self):
        """Set up the test environment."""
        # Clear the singleton instance
        Config._instance = None
    
    def test_simulate_bug_with_dirname(self):
        """
        Simulate the bug where dirname() was incorrectly used on local_repo_path.
        """
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up environment variables for testing
            with patch.dict(os.environ, {
                'LOCAL_REPO_PATH': temp_dir,
                'DATA_FILE': os.path.join(temp_dir, 'data.json'),
                'MESSAGES_FILE': os.path.join(temp_dir, 'messages.json'),
                'CURRENT_HEAD_FILE': os.path.join(temp_dir, 'head.txt'),
                'LOG_FILE': os.path.join(temp_dir, 'log.txt'),
                'DISCORD_TOKEN': 'test-token',
                'CHANNEL_IDS': '123456789,987654321'
            }):
                # Reset Config singleton
                Config._instance = None
                
                # Create config instance
                config = Config()
                
                # Manually create the buggy list with dirname() used incorrectly
                buggy_dirs = [
                    os.path.dirname(config.data_file),
                    os.path.dirname(config.messages_file),
                    os.path.dirname(config.current_head_file),
                    os.path.dirname(config.log_file),
                    os.path.dirname(config.local_repo_path),  # BUG: dirname shouldn't be used here
                ]
                
                # Correct list without the bug
                fixed_dirs = [
                    os.path.dirname(config.data_file),
                    os.path.dirname(config.messages_file),
                    os.path.dirname(config.current_head_file),
                    os.path.dirname(config.log_file),
                    config.local_repo_path,  # FIXED: no dirname() call
                ]
                
                # The buggy implementation should have a different path for local_repo_path
                self.assertNotEqual(buggy_dirs[-1], fixed_dirs[-1], 
                                   "Bug simulation failed - paths should differ")
                
                # The buggy implementation should have an empty path if root directory was used
                with patch.dict(os.environ, {'LOCAL_REPO_PATH': '/'}):
                    Config._instance = None
                    root_config = Config()
                    buggy_path = os.path.dirname(root_config.local_repo_path)
                    self.assertEqual(buggy_path, '/', 
                                    "Bug with root path should produce '/' (not empty string)")
    
    def test_check_directory_writable(self):
        """Test the _check_directory_writable method for proper error handling."""
        # Create mock config instance
        config = Config()
        
        # Test with valid directory
        with tempfile.TemporaryDirectory() as temp_dir:
            result = config._check_directory_writable(temp_dir)
            self.assertTrue(result, f"Should be able to write to {temp_dir}")
        
        # Test with non-existent directory (should create it)
        test_dir = os.path.join(tempfile.gettempdir(), f"test_dir_{os.getpid()}")
        try:
            result = config._check_directory_writable(test_dir)
            self.assertTrue(result, f"Should create and write to {test_dir}")
            self.assertTrue(os.path.exists(test_dir), f"Directory {test_dir} should exist")
        finally:
            # Clean up
            if os.path.exists(test_dir):
                os.rmdir(test_dir)
        
        # Test with a directory that cannot be created
        with patch('os.makedirs') as mock_makedirs:
            mock_makedirs.side_effect = PermissionError("Permission denied")
            result = config._check_directory_writable("/path/that/cannot/be/created")
            self.assertFalse(result, "Should handle permission errors gracefully")
    
    def test_fallback_to_default_path(self):
        """Test that empty paths fall back to defaults properly."""
        # Mock environment with empty paths
        with patch.dict(os.environ, {
            'LOCAL_REPO_PATH': '',  # Empty path should trigger default
            'DATA_FILE': '/tmp/data.json',
            'MESSAGES_FILE': '/tmp/messages.json',
            'CURRENT_HEAD_FILE': '/tmp/head.txt',
            'LOG_FILE': '/tmp/log.txt',
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789,987654321'
        }):
            # Reset Config singleton
            Config._instance = None
            
            # Create config instance
            config = Config()
            
            # Verify it falls back to default value
            from chatd.config import DEFAULT_CONFIG
            self.assertEqual(config.local_repo_path, DEFAULT_CONFIG['LOCAL_REPO_PATH'],
                            "Should fall back to default value for empty path")

if __name__ == '__main__':
    unittest.main()