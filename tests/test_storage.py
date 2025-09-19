"""
Tests for storage operations.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from chatd.storage import FileStorage, StorageFactory, get_storage


class TestFileStorage(unittest.TestCase):
    """Test cases for FileStorage implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.temp_dir, 'test_data.json')
        self.messages_file = os.path.join(self.temp_dir, 'test_messages.json')
        self.storage = FileStorage(data_file=self.data_file, messages_file=self.messages_file)
        
        self.sample_data = [
            {
                'company_name': 'Test Company',
                'title': 'Software Engineer',
                'url': 'https://example.com'
            }
        ]
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_data_success(self):
        """Test successful data saving."""
        result = self.storage.save_data(self.sample_data)
        
        self.assertTrue(result)
        
        # Verify file was created and contains correct data
        self.assertTrue(os.path.exists(self.data_file))
        
        with open(self.data_file, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data, self.sample_data)
    
    def test_load_data_success(self):
        """Test successful data loading."""
        # First save some data
        self.storage.save_data(self.sample_data)
        
        # Then load it back
        loaded_data = self.storage.load_data()
        
        self.assertEqual(loaded_data, self.sample_data)
    
    def test_load_data_no_file(self):
        """Test loading data when file doesn't exist."""
        loaded_data = self.storage.load_data()
        
        self.assertEqual(loaded_data, [])
    
    def test_load_data_invalid_json(self):
        """Test loading data with invalid JSON."""
        # Create file with invalid JSON
        with open(self.data_file, 'w') as f:
            f.write('invalid json content')
        
        loaded_data = self.storage.load_data()
        
        self.assertEqual(loaded_data, [])
    
    def test_save_message_info_success(self):
        """Test successful message info saving."""
        result = self.storage.save_message_info('12345', '67890', 'test_role')
        
        self.assertTrue(result)
        
        # Verify file was created
        self.assertTrue(os.path.exists(self.messages_file))
        
        with open(self.messages_file, 'r') as f:
            tracking_data = json.load(f)
        
        # Data is stored as a dictionary by role_key
        self.assertIn('test_role', tracking_data)
        self.assertEqual(len(tracking_data['test_role']), 1)
        self.assertEqual(tracking_data['test_role'][0]['message_id'], '12345')
        self.assertEqual(tracking_data['test_role'][0]['channel_id'], '67890')
    
    def test_save_message_info_append(self):
        """Test appending message info to existing data."""
        # Save first message
        self.storage.save_message_info('12345', '67890', 'role1')
        
        # Save second message
        self.storage.save_message_info('54321', '09876', 'role2')
        
        with open(self.messages_file, 'r') as f:
            tracking_data = json.load(f)
        
        # Should have two role keys
        self.assertEqual(len(tracking_data), 2)
        self.assertIn('role1', tracking_data)
        self.assertIn('role2', tracking_data)
    
    def test_get_messages_for_role(self):
        """Test retrieving messages for a specific role."""
        # Save multiple messages
        self.storage.save_message_info('12345', '67890', 'role1')
        self.storage.save_message_info('54321', '09876', 'role2')
        self.storage.save_message_info('99999', '11111', 'role1')
        
        messages = self.storage.get_messages_for_role('role1')
        
        self.assertEqual(len(messages), 2)
        message_ids = [msg['message_id'] for msg in messages]
        self.assertIn('12345', message_ids)
        self.assertIn('99999', message_ids)
    
    def test_get_messages_for_role_no_matches(self):
        """Test retrieving messages when no matches exist."""
        self.storage.save_message_info('12345', '67890', 'role1')
        
        messages = self.storage.get_messages_for_role('nonexistent_role')
        
        self.assertEqual(messages, [])
    
    def test_get_messages_for_role_no_file(self):
        """Test retrieving messages when tracking file doesn't exist."""
        messages = self.storage.get_messages_for_role('any_role')
        
        self.assertEqual(messages, [])
    
    @patch('builtins.open', side_effect=PermissionError())
    def test_save_data_permission_error(self, mock_open):
        """Test data saving with permission error."""
        result = self.storage.save_data(self.sample_data)
        
        self.assertFalse(result)
    
    @patch('builtins.open', side_effect=OSError())
    def test_save_message_info_os_error(self, mock_open):
        """Test message info saving with OS error."""
        result = self.storage.save_message_info('12345', '67890', 'test_role')
        
        self.assertFalse(result)


class TestStorageFactory(unittest.TestCase):
    """Test cases for StorageFactory."""
    
    def test_create_file_storage(self):
        """Test creating file storage."""
        storage = StorageFactory.create_storage('file')
        
        self.assertIsInstance(storage, FileStorage)
    
    def test_create_unsupported_storage(self):
        """Test creating unsupported storage type."""
        storage = StorageFactory.create_storage('redis')
        
        # Should fall back to file storage
        self.assertIsInstance(storage, FileStorage)
    
    def test_create_storage_with_kwargs(self):
        """Test creating storage with keyword arguments."""
        temp_dir = tempfile.mkdtemp()
        try:
            data_file = os.path.join(temp_dir, 'test_data.json')
            storage = StorageFactory.create_storage('file', data_file=data_file)
            
            self.assertIsInstance(storage, FileStorage)
            # Test that the custom data_file was used
            result = storage.save_data([{'test': 'data'}])
            self.assertTrue(result)
            
            self.assertTrue(os.path.exists(data_file))
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestStorageSingleton(unittest.TestCase):
    """Test cases for storage singleton behavior."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear the singleton instance
        import chatd.storage
        chatd.storage._storage_instance = None
    
    def tearDown(self):
        """Clean up after tests."""
        # Clear the singleton instance
        import chatd.storage
        chatd.storage._storage_instance = None
    
    def test_get_storage_singleton(self):
        """Test that get_storage returns the same instance."""
        storage1 = get_storage()
        storage2 = get_storage()
        
        self.assertIs(storage1, storage2)
    
    def test_get_storage_with_type(self):
        """Test get_storage with storage type parameter."""
        storage = get_storage('file')
        
        self.assertIsInstance(storage, FileStorage)
    
    def test_get_storage_with_kwargs(self):
        """Test get_storage with keyword arguments."""
        temp_dir = tempfile.mkdtemp()
        try:
            data_file = os.path.join(temp_dir, 'test_data.json')
            storage = get_storage('file', data_file=data_file)
            
            self.assertIsInstance(storage, FileStorage)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestStorageIntegration(unittest.TestCase):
    """Integration tests for storage system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        import chatd.storage
        chatd.storage._storage_instance = None
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        import chatd.storage
        chatd.storage._storage_instance = None
    
    def test_complete_workflow(self):
        """Test complete storage workflow."""
        temp_dir = tempfile.mkdtemp()
        try:
            data_file = os.path.join(temp_dir, 'workflow_data.json')
            messages_file = os.path.join(temp_dir, 'workflow_messages.json')
            
            # Create a fresh storage instance instead of using singleton
            storage = FileStorage(data_file=data_file, messages_file=messages_file)
            
            # Test data operations
            test_data = [
                {'company': 'Company A', 'title': 'Role A'},
                {'company': 'Company B', 'title': 'Role B'}
            ]
            
            # Save and load data
            self.assertTrue(storage.save_data(test_data))
            loaded_data = storage.load_data()
            self.assertEqual(loaded_data, test_data)
            
            # Test message tracking
            self.assertTrue(storage.save_message_info('msg1', 'ch1', 'workflow_role_a'))
            self.assertTrue(storage.save_message_info('msg2', 'ch1', 'workflow_role_b'))
            self.assertTrue(storage.save_message_info('msg3', 'ch2', 'workflow_role_a'))
            
            # Retrieve messages for specific role
            role_a_messages = storage.get_messages_for_role('workflow_role_a')
            self.assertEqual(len(role_a_messages), 2)
            
            role_b_messages = storage.get_messages_for_role('workflow_role_b')
            self.assertEqual(len(role_b_messages), 1)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_concurrent_access(self):
        """Test concurrent access to storage (basic thread safety)."""
        import threading
        import time
        
        temp_dir = tempfile.mkdtemp()
        try:
            data_file = os.path.join(temp_dir, 'test_data.json')
            storage = get_storage('file', data_file=data_file)
            results = []
            
            def save_data_worker(worker_id):
                try:
                    data = [{'worker': worker_id, 'timestamp': time.time()}]
                    result = storage.save_data(data)
                    results.append(result)
                except Exception as e:
                    results.append(False)
            
            # Create multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=save_data_worker, args=(i,))
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # At least some operations should succeed
            # (Due to file locking, not all may succeed, but that's expected)
            self.assertTrue(any(results))
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
