"""
Tests for Phase 10.6: Database Update Support

Tests change detection, update handling, and idempotent operations.
"""

import pytest
import tempfile
import json
import time
import copy
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from chatd.storage_abstraction import DataStorage, JsonStorageBackend, DatabaseStorageBackend
from chatd.config import Config


@pytest.fixture
def temp_json_files():
    """Create temporary JSON files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        data_file = Path(temp_dir) / "data.json"
        messages_file = Path(temp_dir) / "messages.json"
        yield str(data_file), str(messages_file)


@pytest.fixture
def mock_config(temp_json_files):
    """Create a mock config for testing."""
    data_file, messages_file = temp_json_files
    config = Mock(spec=Config)
    config.data_file = data_file
    config.messages_file = messages_file
    config.migration_mode = 'json_only'
    return config


@pytest.fixture
def sample_jobs():
    """Sample job postings for testing."""
    return [
        {
            'id': 'job1',
            'date_updated': 1695000000,
            'url': 'https://company1.com/job1',
            'company_name': 'Company 1',
            'title': 'Software Engineer',
            'active': True,
            'is_visible': True,
            'locations': ['San Francisco, CA'],
            'terms': ['Internship']
        },
        {
            'id': 'job2',
            'date_updated': 1695000001,
            'url': 'https://company2.com/job2',
            'company_name': 'Company 2',
            'title': 'Data Scientist',
            'active': True,
            'is_visible': True,
            'locations': ['New York, NY'],
            'terms': ['Full-time']
        }
    ]


@pytest.fixture
def json_backend(temp_json_files):
    """Create a JSON storage backend for testing."""
    data_file, messages_file = temp_json_files
    return JsonStorageBackend(data_file, messages_file)


class TestChangeDetection:
    """Test change detection functionality."""
    
    def test_detect_no_changes(self, json_backend, sample_jobs):
        """Test that no changes are detected when data is identical."""
        current_jobs = sample_jobs.copy()
        previous_jobs = sample_jobs.copy()
        
        changes = json_backend.detect_job_changes(current_jobs, previous_jobs)
        
        assert changes['added'] == []
        assert changes['updated'] == []
        assert changes['removed'] == []
    
    def test_detect_added_jobs(self, json_backend, sample_jobs):
        """Test detection of new job postings."""
        previous_jobs = sample_jobs[:1]  # Only first job
        current_jobs = sample_jobs  # Both jobs
        
        changes = json_backend.detect_job_changes(current_jobs, previous_jobs)
        
        assert len(changes['added']) == 1
        assert changes['added'][0]['id'] == 'job2'
        assert changes['updated'] == []
        assert changes['removed'] == []
    
    def test_detect_removed_jobs(self, json_backend, sample_jobs):
        """Test detection of removed job postings."""
        previous_jobs = sample_jobs  # Both jobs
        current_jobs = sample_jobs[:1]  # Only first job
        
        changes = json_backend.detect_job_changes(current_jobs, previous_jobs)
        
        assert changes['added'] == []
        assert changes['updated'] == []
        assert len(changes['removed']) == 1
        assert changes['removed'][0]['id'] == 'job2'
    
    def test_detect_active_change(self, json_backend, sample_jobs):
        """Test detection of active field changes."""
        previous_jobs = copy.deepcopy(sample_jobs)
        current_jobs = copy.deepcopy(sample_jobs)
        current_jobs[0]['active'] = False  # Change job1 to inactive
        
        changes = json_backend.detect_job_changes(current_jobs, previous_jobs)
        
        assert changes['added'] == []
        assert changes['removed'] == []
        assert len(changes['updated']) == 1
        
        update_info = changes['updated'][0]
        assert update_info['job']['id'] == 'job1'
        assert 'active' in update_info['changes']
        assert update_info['changes']['active']['old'] is True
        assert update_info['changes']['active']['new'] is False
    
    def test_detect_visibility_change(self, json_backend, sample_jobs):
        """Test detection of is_visible field changes."""
        previous_jobs = copy.deepcopy(sample_jobs)
        current_jobs = copy.deepcopy(sample_jobs)
        current_jobs[1]['is_visible'] = False  # Hide job2
        
        changes = json_backend.detect_job_changes(current_jobs, previous_jobs)
        
        assert len(changes['updated']) == 1
        update_info = changes['updated'][0]
        assert update_info['job']['id'] == 'job2'
        assert 'is_visible' in update_info['changes']
        assert update_info['changes']['is_visible']['old'] is True
        assert update_info['changes']['is_visible']['new'] is False
    
    def test_detect_content_correction(self, json_backend, sample_jobs):
        """Test detection of content corrections (date_updated changes)."""
        previous_jobs = copy.deepcopy(sample_jobs)
        current_jobs = copy.deepcopy(sample_jobs)
        
        # Simulate content correction: update timestamp and title
        current_jobs[0]['date_updated'] = 1695000010
        current_jobs[0]['title'] = 'Senior Software Engineer'
        current_jobs[0]['locations'] = ['San Francisco, CA', 'Remote']
        
        changes = json_backend.detect_job_changes(current_jobs, previous_jobs)
        
        assert len(changes['updated']) == 1
        update_info = changes['updated'][0]
        assert update_info['job']['id'] == 'job1'
        
        # Should detect date_updated change and all content changes
        assert 'date_updated' in update_info['changes']
        assert 'title' in update_info['changes']
        assert 'locations' in update_info['changes']
        
        assert update_info['changes']['title']['old'] == 'Software Engineer'
        assert update_info['changes']['title']['new'] == 'Senior Software Engineer'


class TestUpdateOperations:
    """Test update operations functionality."""
    
    def test_json_update_job_posting(self, json_backend, sample_jobs):
        """Test updating job postings in JSON backend."""
        # Save initial jobs
        json_backend.save_job_postings(sample_jobs)
        
        # Update job1 active status
        success = json_backend.update_job_posting('job1', {'active': False})
        assert success
        
        # Verify the update
        updated_jobs = json_backend.get_job_postings()
        job1 = next(job for job in updated_jobs if job['id'] == 'job1')
        assert job1['active'] is False
        
        # Job2 should remain unchanged
        job2 = next(job for job in updated_jobs if job['id'] == 'job2')
        assert job2['active'] is True
    
    def test_json_update_nonexistent_job(self, json_backend, sample_jobs):
        """Test updating a non-existent job posting."""
        json_backend.save_job_postings(sample_jobs)
        
        success = json_backend.update_job_posting('nonexistent', {'active': False})
        assert not success
    
    @patch('chatd.storage_abstraction.create_database_manager')
    def test_database_update_job_posting(self, mock_create_db):
        """Test updating job postings in database backend."""
        # Mock database manager and session
        mock_db_manager = Mock()
        mock_session = Mock()
        mock_create_db.return_value = mock_db_manager
        mock_db_manager.session_scope.return_value.__enter__ = Mock(return_value=mock_session)
        mock_db_manager.session_scope.return_value.__exit__ = Mock(return_value=None)
        mock_db_manager.test_connection.return_value = True
        
        # Mock job posting query
        mock_job_posting = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_job_posting
        
        # Create database backend
        db_backend = DatabaseStorageBackend(mock_db_manager)
        
        # Test update
        success = db_backend.update_job_posting('job1', {'active': False})
        assert success
        
        # Verify the job posting was updated
        assert mock_job_posting.active is False


class TestDataStorageIntegration:
    """Test DataStorage class integration with update support."""
    
    def test_process_job_changes_new_jobs(self, mock_config, sample_jobs):
        """Test processing new job additions."""
        storage = DataStorage(mock_config)
        
        # Start with empty storage
        results = storage.process_job_changes(sample_jobs)
        
        assert results['added_count'] == 2
        assert results['updated_count'] == 0
        assert results['removed_count'] == 0
        assert results['success'] is True
        
        # Verify jobs were saved
        stored_jobs = storage.get_job_postings()
        assert len(stored_jobs) == 2
    
    def test_process_job_changes_updates(self, mock_config, sample_jobs):
        """Test processing job updates."""
        storage = DataStorage(mock_config)
        
        # Save initial jobs
        storage.save_job_postings(sample_jobs)
        
        # Modify jobs
        updated_jobs = copy.deepcopy(sample_jobs)
        updated_jobs[0]['active'] = False
        updated_jobs[1]['is_visible'] = False
        
        results = storage.process_job_changes(updated_jobs)
        
        assert results['added_count'] == 0
        assert results['updated_count'] == 2
        assert results['removed_count'] == 0
        assert results['success'] is True
        
        # Verify updates were applied
        stored_jobs = storage.get_job_postings()
        job1 = next(job for job in stored_jobs if job['id'] == 'job1')
        job2 = next(job for job in stored_jobs if job['id'] == 'job2')
        assert job1['active'] is False
        assert job2['is_visible'] is False
    
    def test_idempotent_operations(self, mock_config, sample_jobs):
        """Test that update operations are idempotent."""
        storage = DataStorage(mock_config)
        
        # Save initial jobs
        storage.save_job_postings(sample_jobs)
        
        # Process the same jobs multiple times
        results1 = storage.process_job_changes(sample_jobs)
        results2 = storage.process_job_changes(sample_jobs)
        results3 = storage.process_job_changes(sample_jobs)
        
        # Should detect no changes after first run
        assert results1['updated_count'] == 0  # No changes on identical data
        assert results2['updated_count'] == 0
        assert results3['updated_count'] == 0
        
        # Storage should remain unchanged
        final_jobs = storage.get_job_postings()
        assert len(final_jobs) == 2
    
    def test_concurrent_change_handling(self, mock_config, sample_jobs):
        """Test handling of concurrent changes gracefully."""
        storage = DataStorage(mock_config)
        
        # Save initial jobs
        storage.save_job_postings(sample_jobs)
        
        # Simulate concurrent updates
        update1 = copy.deepcopy(sample_jobs)
        update1[0]['active'] = False
        
        update2 = copy.deepcopy(sample_jobs)
        update2[0]['is_visible'] = False
        
        # Apply updates sequentially (simulating concurrent scenario)
        results1 = storage.process_job_changes(update1)
        results2 = storage.process_job_changes(update2)
        
        assert results1['success'] is True
        assert results2['success'] is True
        
        # Final state should reflect the last update
        final_jobs = storage.get_job_postings()
        job1 = next(job for job in final_jobs if job['id'] == 'job1')
        assert job1['is_visible'] is False