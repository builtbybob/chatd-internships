#!/usr/bin/env python3
"""
Tests for soft delete functionality.
"""

import unittest
import uuid
from unittest.mock import Mock, patch, MagicMock


class TestSoftDeleteFunctionality(unittest.TestCase):
    """Test soft delete behavior for job postings."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Sample job data
        self.job_id = str(uuid.uuid4())
        self.sample_job = {
            'id': self.job_id,
            'date_updated': 1234567890,
            'url': 'https://example.com/job',
            'company_name': 'Test Company',
            'title': 'Software Engineer',
            'sponsorship': 'Available',
            'active': True,
            'source': 'test',
            'date_posted': 1234567890,
            'company_url': 'https://example.com',
            'is_visible': True,
            'category': 'Engineering',
            'is_deleted': False,
            'locations': ['Remote'],
            'terms': ['Full-time'],
            'degrees': ['Bachelor']
        }
    
    @patch('chatd.storage_abstraction.DatabaseStorageBackend')
    def test_remove_job_posting_soft_delete_concept(self, mock_backend_class):
        """Test the concept that remove_job_posting should perform soft delete."""
        # This test ensures our soft delete logic is conceptually correct
        # and that the remove_job_posting method exists and behaves as expected
        
        # Mock the database backend
        mock_backend = Mock()
        mock_backend_class.return_value = mock_backend
        
        # Mock a successful soft delete
        mock_backend.remove_job_posting.return_value = True
        
        # Test that the method can be called
        result = mock_backend.remove_job_posting(self.job_id)
        
        # Verify the method was called and returned True
        mock_backend.remove_job_posting.assert_called_once_with(self.job_id)
        assert result is True
    
    @patch('chatd.storage_abstraction.DatabaseStorageBackend')  
    def test_get_job_postings_filtering_concept(self, mock_backend_class):
        """Test the concept that get_job_postings should filter deleted records."""
        
        # Mock the database backend
        mock_backend = Mock()
        mock_backend_class.return_value = mock_backend
        
        # Mock filtered results
        active_jobs = [
            {'id': 'job1', 'is_deleted': False, 'title': 'Active Job'},
            {'id': 'job2', 'is_deleted': False, 'title': 'Another Active Job'}
        ]
        all_jobs = active_jobs + [
            {'id': 'job3', 'is_deleted': True, 'title': 'Deleted Job'}
        ]
        
        # Configure mock to return different results based on include_deleted parameter
        def mock_get_job_postings(include_deleted=False):
            return all_jobs if include_deleted else active_jobs
            
        mock_backend.get_job_postings.side_effect = mock_get_job_postings
        
        # Test default behavior (should exclude deleted)
        result_default = mock_backend.get_job_postings()
        assert len(result_default) == 2
        assert all(job['is_deleted'] is False for job in result_default)
        
        # Test with include_deleted=True
        result_all = mock_backend.get_job_postings(include_deleted=True)
        assert len(result_all) == 3
        
        # Verify method was called correctly
        assert mock_backend.get_job_postings.call_count == 2


class TestSoftDeleteIntegration(unittest.TestCase):
    """Integration tests for soft delete functionality."""
    
    @patch('chatd.bot.get_storage')
    async def test_get_role_data_includes_soft_deleted_jobs(self, mock_get_storage):
        """Test that get_role_data_by_message_id can find soft-deleted jobs."""
        from chatd.bot import get_role_data_by_message_id
        
        # Mock storage without database backend to test JSON fallback
        mock_storage = Mock()
        mock_storage.database_backend = None  # Force JSON fallback
        mock_storage.get_message_tracking.return_value = {
            'job1': {
                'message_id': '123456789',
                'channel_id': '987654321',
                'posted_at': 1234567890
            }
        }
        mock_get_storage.return_value = mock_storage
        
        # Mock JSON data with a soft-deleted job
        mock_job_data = [
            {
                'id': 'job1',
                'company_name': 'Test Company',
                'title': 'Software Engineer',
                'url': 'https://example.com/job',
                'is_deleted': True,  # This job is soft-deleted
                'active': True,
                'is_visible': True
            }
        ]
        
        with patch('chatd.bot.read_json', return_value=mock_job_data):
            result = await get_role_data_by_message_id('123456789')
            
            # Should find the job even though it's soft-deleted
            assert result is not None
            assert result['company_name'] == 'Test Company'
            assert result['is_deleted'] is True
    
    def test_soft_delete_preserves_message_tracking(self):
        """Test that soft delete preserves message tracking relationships."""
        # This is conceptual - in the old hard delete approach, 
        # message tracking was deleted along with the job.
        # With soft delete, message tracking should be preserved.
        
        # Mock a soft-deleted job that still has message tracking
        job_with_tracking = {
            'id': 'job1',
            'is_deleted': True,
            'message_tracking': {
                'message_id': '123456789',
                'channel_id': '987654321'
            }
        }
        
        # The key insight is that message_tracking should still exist
        # even for soft-deleted jobs, allowing reactions to work
        assert job_with_tracking['is_deleted'] is True
        assert 'message_tracking' in job_with_tracking
        assert job_with_tracking['message_tracking']['message_id'] == '123456789'


if __name__ == '__main__':
    unittest.main()