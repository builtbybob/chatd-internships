"""
Tests for the directory validation in config module.
"""

import os
import unittest
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from chatd.config import Config


class TestFilePermissionsValidation(unittest.TestCase):
    """Test cases for the file permissions validation in Config class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Clear the singleton instance
        Config._instance = None
        
        # Configure basic logging for tests
        logging.basicConfig(level=logging.INFO, 
                           format='[%(asctime)s] [%(levelname)-7s] %(name)s: %(message)s')
        
        # Mock environment variables including Docker-like paths
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789,987654321',
            'LOG_LEVEL': 'DEBUG',
            'LOCAL_REPO_PATH': '/app/Summer2026-Internships',
            'DATA_FILE': '/app/data/previous_data.json',
            'MESSAGES_FILE': '/app/data/message_tracking.json',
            'CURRENT_HEAD_FILE': '/app/data/current_head.txt',
            'LOG_FILE': '/app/logs/chatd.log',
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up after the test."""
        self.env_patcher.stop()
    
    @patch('os.makedirs')
    @patch('os.path.dirname')
    def test_directory_paths(self, mock_dirname, mock_makedirs):
        """Test that directory paths are correctly generated."""
        # Configure mocks
        mock_dirname.side_effect = lambda path: os.path.split(path)[0]
        
        # Create config instance
        config = Config()
        
        # Verify local_repo_path is handled correctly
        self.assertEqual(config.local_repo_path, '/app/Summer2026-Internships')
        
        # Mock the directory writable check to return True
        with patch.object(config, '_check_directory_writable', return_value=True):
            # Call the validation method
            result = config._validate_file_permissions()
            
            # Verify it passes
            self.assertTrue(result)
            
            # Check _check_directory_writable was called with correct paths
            expected_dirs = [
                '/app/data',  # dirname of data_file
                '/app/data',  # dirname of messages_file
                '/app/data',  # dirname of current_head_file
                '/app/logs',  # dirname of log_file
                '/app/Summer2026-Internships'  # local_repo_path directly (not dirname)
            ]
            
            # Get the actual calls
            calls = [args[0] for args, _ in config._check_directory_writable.call_args_list]
            
            # Verify the calls match the expected directories
            self.assertEqual(len(calls), len(expected_dirs))
            for expected, actual in zip(expected_dirs, calls):
                self.assertEqual(expected, actual)
    
    @patch('os.makedirs')
    @patch('builtins.open')
    @patch('os.remove')
    def test_check_directory_writable(self, mock_remove, mock_file, mock_makedirs):
        """Test the _check_directory_writable method."""
        # Create config instance
        config = Config()
        
        # Set up mock_file to return a context manager
        mock_file.return_value.__enter__.return_value.write = MagicMock()
        
        # Test with valid directory
        result = config._check_directory_writable('/app/test')
        self.assertTrue(result)
        mock_makedirs.assert_called_with('/app/test', exist_ok=True)
        # Verify open was called with the test file
        test_file_call = False
        for call in mock_file.call_args_list:
            args, kwargs = call
            if args and '/app/test/.write_test' in args[0] and 'w' in args[1:]:
                test_file_call = True
                break
        self.assertTrue(test_file_call, "open() was not called with the test file path")
        self.assertIn(mock_remove.call_args[0][0], '/app/test/.write_test')
        
        # Reset mocks
        mock_makedirs.reset_mock()
        mock_file.reset_mock()
        mock_remove.reset_mock()
        
        # Test with an error during directory creation
        mock_makedirs.side_effect = PermissionError("Permission denied")
        result = config._check_directory_writable('/app/test')
        self.assertFalse(result)
        mock_makedirs.assert_called_with('/app/test', exist_ok=True)
    
    def test_empty_paths(self):
        """Test validation with empty paths."""
        # Create config instance
        config = Config()
        
        # Test with an empty local_repo_path
        config.local_repo_path = ""
        result = config._validate_file_permissions()
        self.assertFalse(result)
    
    def test_with_valid_repo_dir(self):
        """Test validation with a valid repository directory."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up environment variables for testing
            with patch.dict(os.environ, {
                'LOCAL_REPO_PATH': temp_dir,
                'DATA_FILE': os.path.join(temp_dir, 'data.json'),
                'MESSAGES_FILE': os.path.join(temp_dir, 'messages.json'),
                'CURRENT_HEAD_FILE': os.path.join(temp_dir, 'head.txt'),
                'LOG_FILE': os.path.join(temp_dir, 'log.txt'),
                'DISCORD_TOKEN': 'test-token-for-validation-only',
                'CHANNEL_IDS': '123456789012345678,987654321098765432'
            }):
                # Reset Config singleton to load new env vars
                Config._instance = None
                
                # Create config instance
                config = Config()
                
                # Test just the file permissions validation
                result = config._validate_file_permissions()
                
                # Verify required directories were checked correctly
                required_dirs = [
                    os.path.dirname(config.data_file),
                    os.path.dirname(config.messages_file),
                    os.path.dirname(config.current_head_file),
                    os.path.dirname(config.log_file),
                    config.local_repo_path,  # This is the key one - no dirname call
                ]
                
                # Check paths are all valid
                for dir_path in required_dirs:
                    self.assertTrue(dir_path and dir_path.strip() != '', 
                                  f"Directory path should not be empty: {dir_path}")
                
                self.assertTrue(result, "Validation should pass with valid directory")
    
    def test_root_directory_path(self):
        """Test validation with a root-level directory path."""
        # Test with /tmp which should be accessible
        with patch.dict(os.environ, {
            'LOCAL_REPO_PATH': '/tmp',
            'DATA_FILE': '/tmp/data.json',
            'MESSAGES_FILE': '/tmp/messages.json',
            'CURRENT_HEAD_FILE': '/tmp/head.txt',
            'LOG_FILE': '/tmp/log.txt',
            'DISCORD_TOKEN': 'test-token-for-validation-only',
            'CHANNEL_IDS': '123456789012345678,987654321098765432'
        }):
            # Reset Config singleton
            Config._instance = None
            
            # Create config instance
            config = Config()
            
            # Verify dirname would cause problems on root path
            dirname_path = os.path.dirname(config.local_repo_path)
            self.assertEqual(dirname_path, '/', 
                            "os.path.dirname('/tmp') should return '/'")
            
            # Test fixed validation (without dirname)
            result = config._validate_file_permissions()
            self.assertTrue(result, "Validation should pass with root directory")
    
    def test_empty_path_handling(self):
        """Test that empty paths are handled correctly (should fail, not error)."""
        # Set up environment variables with an empty path
        with patch.dict(os.environ, {
            'LOCAL_REPO_PATH': '',  # Empty path
            'DATA_FILE': '/tmp/data.json',
            'MESSAGES_FILE': '/tmp/messages.json',
            'CURRENT_HEAD_FILE': '/tmp/head.txt',
            'LOG_FILE': '/tmp/log.txt',
            'DISCORD_TOKEN': 'test-token-for-validation-only',
            'CHANNEL_IDS': '123456789012345678,987654321098765432'
        }):
            # Reset Config singleton
            Config._instance = None
            
            # Create config instance
            config = Config()
            
            # The validation should return False for an empty path, not raise an exception
            result = config._validate_file_permissions()
            self.assertFalse(result, "Validation should fail with empty path")


if __name__ == '__main__':
    unittest.main()