"""
Tests for repository operations module.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import git

from chatd.repo import clone_or_update_repo, read_json


class TestRepositoryOperations(unittest.TestCase):
    """Test cases for repository operations."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token',
            'CHANNEL_IDS': '123456789',
            'REPO_URL': 'https://github.com/test/repo.git',
            'LOCAL_REPO_PATH': 'test-repo'
        })
        self.env_patcher.start()
        
        # Reset config singleton
        from chatd.config import Config
        Config._instance = None
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        from chatd.config import Config
        Config._instance = None
    
    @patch('chatd.repo.git.Repo')
    @patch('chatd.repo.os.path.exists')
    def test_clone_repo_fresh(self, mock_exists, mock_repo_class):
        """Test cloning a repository when it doesn't exist locally."""
        mock_exists.return_value = False
        mock_repo_instance = MagicMock()
        mock_repo_class.clone_from.return_value = mock_repo_instance
        
        result = clone_or_update_repo()
        
        self.assertTrue(result)
        mock_repo_class.clone_from.assert_called_once()
    
    @patch('chatd.repo.git.Repo')
    @patch('chatd.repo.os.path.exists')
    def test_update_existing_repo_with_changes(self, mock_exists, mock_repo_class):
        """Test updating an existing repository with file changes."""
        mock_exists.return_value = True
        mock_repo_instance = MagicMock()
        mock_repo_class.return_value = mock_repo_instance
        
        # Mock git operations to simulate file changes
        mock_repo_instance.git.rev_parse.side_effect = ['old_hash', 'new_hash']
        mock_repo_instance.remotes.origin.pull.return_value = None
        
        result = clone_or_update_repo()
        
        self.assertTrue(result)  # Should return True when file changed
        mock_repo_instance.remotes.origin.pull.assert_called_once()
    
    @patch('chatd.repo.git.Repo')
    @patch('chatd.repo.os.path.exists')
    def test_update_existing_repo_no_changes(self, mock_exists, mock_repo_class):
        """Test updating an existing repository with no file changes."""
        mock_exists.return_value = True
        mock_repo_instance = MagicMock()
        mock_repo_class.return_value = mock_repo_instance
        
        # Mock git operations to simulate no file changes
        mock_repo_instance.git.rev_parse.return_value = 'same_hash'
        mock_repo_instance.remotes.origin.pull.return_value = None
        
        result = clone_or_update_repo()
        
        self.assertFalse(result)  # Should return False when no changes
        mock_repo_instance.remotes.origin.pull.assert_called_once()
    
    @patch('chatd.repo.git.Repo')
    @patch('chatd.repo.os.path.exists')
    @patch('chatd.repo.os.rmdir')
    def test_handle_invalid_repo(self, mock_rmdir, mock_exists, mock_repo_class):
        """Test handling invalid repository directory."""
        mock_exists.return_value = True
        
        # First instantiation raises InvalidGitRepositoryError
        mock_repo_class.side_effect = git.exc.InvalidGitRepositoryError()
        # But clone_from should succeed
        mock_repo_class.clone_from.return_value = MagicMock()
        
        result = clone_or_update_repo()
        
        self.assertTrue(result)
        mock_rmdir.assert_called_once()
        mock_repo_class.clone_from.assert_called_once()
    
    @patch('builtins.open', new_callable=mock_open, read_data='[{"test": "data"}]')
    @patch('chatd.repo.os.path.exists', return_value=True)
    def test_read_json_success(self, mock_exists, mock_file):
        """Test successful JSON file reading."""
        data = read_json()
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['test'], 'data')
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_read_json_file_not_found(self, mock_file):
        """Test JSON reading when file doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            read_json()
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_read_json_invalid_format(self, mock_file):
        """Test JSON reading with invalid JSON format."""
        with self.assertRaises(Exception):  # json.JSONDecodeError inherits from Exception
            read_json()
    

if __name__ == '__main__':
    unittest.main()
