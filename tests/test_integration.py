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

# Mock storage initialization at module level to prevent file system operations
# This must happen before importing bot module
import sys

# Create a comprehensive mock for JsonStorageBackend that doesn't create directories
class MockJsonStorageBackend:
    def __init__(self, *args, **kwargs):
        self._job_postings = []
        self._message_tracking = {}
    
    def get_job_postings(self):
        return self._job_postings.copy()
    
    def save_job_postings(self, job_postings):
        self._job_postings = job_postings.copy()
        return True
    
    def get_message_tracking(self):
        return self._message_tracking.copy()
    
    def save_message_tracking(self, message_tracking):
        self._message_tracking = message_tracking.copy()
        return True
    
    def get_job_posting_by_id(self, job_id):
        for job in self._job_postings:
            if job['id'] == job_id:
                return job.copy()
        return None
    
    def add_message_tracking(self, job_id, message_id, channel_id):
        self._message_tracking[job_id] = {
            'message_id': message_id,
            'channel_id': channel_id
        }
        return True
    
    def health_check(self):
        return True
    
    def detect_job_changes(self, current_jobs, previous_jobs):
        # Create lookup dictionaries by job ID
        current_by_id = {job['id']: job for job in current_jobs}
        previous_by_id = {job['id']: job for job in previous_jobs}
        
        # Track changes
        changes = {
            'added': [],
            'updated': [],
            'removed': []
        }
        
        # Find added jobs
        for job_id, job in current_by_id.items():
            if job_id not in previous_by_id:
                changes['added'].append(job)
        
        # Find removed jobs
        for job_id, job in previous_by_id.items():
            if job_id not in current_by_id:
                changes['removed'].append(job)
        
        # Find updated jobs (check all fields, not just key fields)
        for job_id, current_job in current_by_id.items():
            if job_id in previous_by_id:
                previous_job = previous_by_id[job_id]
                job_changes = {}
                
                # Check all fields for changes
                all_keys = set(current_job.keys()) | set(previous_job.keys())
                for field in all_keys:
                    if current_job.get(field) != previous_job.get(field):
                        job_changes[field] = {
                            'old': previous_job.get(field),
                            'new': current_job.get(field)
                        }
                
                if job_changes:
                    changes['updated'].append({
                        'id': job_id,
                        'job': current_job,
                        'changes': job_changes
                    })
        
        return changes
    
    def update_job_posting(self, job_id, updates):
        for i, job in enumerate(self._job_postings):
            if job['id'] == job_id:
                self._job_postings[i].update(updates)
                return True
        return False

# Create a comprehensive mock for DataStorage 
class MockDataStorage:
    def __init__(self, *args, **kwargs):
        self._job_postings = []
        self._message_tracking = {}
    
    def get_job_postings(self):
        return self._job_postings.copy()
    
    def save_job_postings(self, job_postings):
        self._job_postings = job_postings.copy()
        return True
    
    def get_message_tracking(self):
        return self._message_tracking.copy()
    
    def save_message_tracking(self, message_tracking):
        self._message_tracking = message_tracking.copy()
        return True
    
    def get_job_posting_by_id(self, job_id):
        for job in self._job_postings:
            if job['id'] == job_id:
                return job.copy()
        return None
    
    def add_message_tracking(self, job_id, message_id, channel_id):
        self._message_tracking[job_id] = {
            'message_id': message_id,
            'channel_id': channel_id
        }
        return True
    
    def health_check(self):
        return {'json': True, 'database': True}
    
    def get_backend_status(self):
        return {'mode': 'json_only', 'backends': {'json': True}}
    
    def detect_job_changes(self, current_jobs):
        # For DataStorage, we compare against stored jobs
        previous_jobs = self._job_postings
        
        # Create lookup dictionaries by job ID
        current_by_id = {job['id']: job for job in current_jobs}
        previous_by_id = {job['id']: job for job in previous_jobs}
        
        # Track changes
        changes = {
            'added': [],
            'removed': [],
            'active_changed': [],
            'visibility_changed': [],
            'content_corrected': []
        }
        
        # Find added jobs
        for job_id, job in current_by_id.items():
            if job_id not in previous_by_id:
                changes['added'].append(job)
        
        # Find removed jobs
        for job_id, job in previous_by_id.items():
            if job_id not in current_by_id:
                changes['removed'].append(job)
        
        # Find updated jobs
        for job_id, current_job in current_by_id.items():
            if job_id in previous_by_id:
                previous_job = previous_by_id[job_id]
                
                # Check for active changes
                if current_job.get('active') != previous_job.get('active'):
                    changes['active_changed'].append({
                        'id': job_id,
                        'job': current_job,
                        'old_active': previous_job.get('active'),
                        'new_active': current_job.get('active')
                    })
                
                # Check for visibility changes
                if current_job.get('is_visible') != previous_job.get('is_visible'):
                    changes['visibility_changed'].append({
                        'id': job_id,
                        'job': current_job,
                        'old_visible': previous_job.get('is_visible'),
                        'new_visible': current_job.get('is_visible')
                    })
                
                # Check for content corrections
                if current_job.get('date_updated', 0) > previous_job.get('date_updated', 0):
                    changes['content_corrected'].append({
                        'id': job_id,
                        'job': current_job,
                        'old_date': previous_job.get('date_updated'),
                        'new_date': current_job.get('date_updated')
                    })
        
        return changes
    
    def update_job_posting(self, job_id, updates):
        for i, job in enumerate(self._job_postings):
            if job['id'] == job_id:
                self._job_postings[i].update(updates)
                return True
        return False
    
    def process_job_changes(self, current_jobs):
        # Detect changes first
        changes = self.detect_job_changes(current_jobs)
        
        # Calculate summary statistics
        summary = {
            'added': len(changes['added']),
            'removed': len(changes['removed']),
            'active_changed': len(changes['active_changed']),
            'visibility_changed': len(changes['visibility_changed']),
            'content_corrected': len(changes['content_corrected'])
        }
        
        # Determine if changes need Discord notification
        changes_for_discord = []
        changes_for_discord.extend(changes['added'])
        changes_for_discord.extend([c['job'] for c in changes['active_changed']])
        changes_for_discord.extend([c['job'] for c in changes['visibility_changed']])
        
        # Save the new data
        self.save_job_postings(current_jobs)
        
        return {
            'changes_detected': bool(changes_for_discord),
            'changes_for_discord': changes_for_discord,
            'full_update_needed': len(changes_for_discord) > 10,
            'summary': summary,
            'added_count': summary['added'],
            'removed_count': summary['removed'], 
            'updated_count': summary['active_changed'] + summary['visibility_changed'] + summary['content_corrected'],
            'success': True
        }

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
        'DISCORD_TOKEN': 'test-token-long-enough-to-pass-validation-checks-1234567890',
        'CHANNEL_IDS': '123456789012345678,987654321098765432',
        'LOG_LEVEL': 'INFO',
        'ENABLE_REACTIONS': 'false',
        'DATA_FILE': '/tmp/test-data/previous_data.json',
        'MESSAGES_FILE': '/tmp/test-data/message_tracking.json',
        'CURRENT_HEAD_FILE': '/tmp/test-data/current_head.txt',
        'LOG_FILE': '/tmp/test-logs/chatd.log',
        'LOCAL_REPO_PATH': '/tmp/test-repo'
    })
    @patch('sys.exit')
    @patch('chatd.config.Config._validate_discord_connection', return_value=True)
    @patch('chatd.config.Config._validate_repository', return_value=True)
    @patch('chatd.config.Config._validate_file_permissions', return_value=True)
    @patch('chatd.config.Config._validate_numeric_config', return_value=True)
    @patch('chatd.config.Config._validate_channel_ids', return_value=True)
    @patch('chatd.config.Config._validate_discord_token', return_value=True)
    def test_config_integration(self, mock_token, mock_channels, mock_numeric, mock_files, mock_repo, mock_discord, mock_exit):
        """Test configuration loading and validation."""
        from chatd.config import Config, validate_config
        
        # Reset singleton to reload with new env vars
        Config._instance = None
        
        config = Config()
        self.assertEqual(config.discord_token, 'test-token-long-enough-to-pass-validation-checks-1234567890')
        self.assertEqual(config.channel_ids, ['123456789012345678', '987654321098765432'])
        self.assertEqual(config.enable_reactions, False)
        
        # Test validation
        result = validate_config()
        # If sys.exit was called, that means validation failed
        mock_exit.assert_not_called()
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
                mock_storage = Mock()
                mock_storage.add_message_tracking.return_value = True
                mock_get_storage.return_value = mock_storage
                
                message = format_message(self.sample_role)
                result = await send_message(message, '123456789', 'test_role_key')
                
                self.assertIsNotNone(result)
                mock_channel.send.assert_called_once_with(message)


if __name__ == '__main__':
    unittest.main()
