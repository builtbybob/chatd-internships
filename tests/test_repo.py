"""
Tests for repository operations module.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import git

from chatd.repo import clone_or_update_repo, read_json, normalize_role_key


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
    
    def test_normalize_role_key_with_url(self):
        """Test role key normalization with URL."""
        role = {
            'company_name': 'TEST COMPANY',
            'title': 'Software Engineer',
            'url': 'https://example.com/job',
            'date_posted': 1725148800.123456
        }
        
        key = normalize_role_key(role)
        expected = 'test company__software engineer__1725148800.123456'
        self.assertEqual(key, expected)
    
    def test_normalize_role_key_without_url(self):
        """Test role key normalization without URL."""
        role = {
            'company_name': 'TEST COMPANY',
            'title': 'Software Engineer',
            'date_posted': 1725148800.123456
        }
        
        key = normalize_role_key(role)
        expected = 'test company__software engineer__1725148800.123456'
        self.assertEqual(key, expected)
    
    def test_normalize_role_key_string_input(self):
        """Test role key normalization with string input."""
        key = normalize_role_key('  Test String  ')
        expected = 'test string'
        self.assertEqual(key, expected)
    
    def test_normalize_role_key_missing_fields(self):
        """Test role key normalization with missing fields."""
        role = {
            'company_name': 'Test Company'
            # Missing title and date_posted
        }
        
        key = normalize_role_key(role)
        expected = 'test company____0'
        self.assertEqual(key, expected)
    
    def test_normalize_role_key_none_values(self):
        """Test role key normalization with None values."""
        role = {
            'company_name': None,
            'title': 'Software Engineer'
            # Missing date_posted (defaults to 0)
        }
        
        key = normalize_role_key(role)
        expected = '__software engineer__0'
        self.assertEqual(key, expected)
        
    def test_normalize_role_key_reopening_scenario(self):
        """Test role key normalization handles re-opening scenario correctly."""
        # Original posting
        role1 = {
            'company_name': 'Meta',
            'title': 'Software Engineer Intern',
            'date_posted': 1725148800.123456
        }
        
        # Re-opening (same role, different date)
        role2 = {
            'company_name': 'Meta',
            'title': 'Software Engineer Intern', 
            'date_posted': 1725840000.789012
        }
        
        key1 = normalize_role_key(role1)
        key2 = normalize_role_key(role2)
        
        # Keys should be different to allow re-opening detection
        self.assertNotEqual(key1, key2)
        self.assertEqual(key1, 'meta__software engineer intern__1725148800.123456')
        self.assertEqual(key2, 'meta__software engineer intern__1725840000.789012')


if __name__ == '__main__':
    unittest.main()
