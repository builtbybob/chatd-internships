"""
Test job resurrection functionality.

This tests the scenario where a soft-deleted job reappears in listings.json
and needs to be "resurrected" (undeleted and updated) rather than added as new.
"""

import pytest
from unittest.mock import MagicMock, patch
from chatd.storage_abstraction import DatabaseStorageBackend
from chatd.database import DatabaseManager, JobPosting


def test_resurrect_soft_deleted_job():
    """Test that attempting to add a soft-deleted job resurrects it instead."""
    
    # Setup mock database manager
    db_manager = MagicMock(spec=DatabaseManager)
    backend = DatabaseStorageBackend(db_manager)
    
    job_id = "test-job-123"
    job_data = {
        'id': job_id,
        'company_name': 'Test Company',
        'title': 'Test Job',
        'url': 'https://example.com/job',
        'date_updated': 1234567890,
        'active': True,
        'locations': ['New York, NY'],
        'terms': ['Summer 2026'],
        'degrees': ["Bachelor's"]
    }
    
    # Mock a soft-deleted job
    mock_job = MagicMock(spec=JobPosting)
    mock_job.id = job_id
    mock_job.is_deleted = True
    
    # Mock session
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_job
    
    # Mock session_scope context manager
    db_manager.session_scope.return_value.__enter__.return_value = mock_session
    db_manager.session_scope.return_value.__exit__.return_value = None
    
    # Mock the resurrect method to return True
    with patch.object(backend, 'resurrect_job_posting', return_value=True) as mock_resurrect:
        # Try to add the job
        success, was_resurrected = backend.add_job_posting(job_data)
        
        # Should have called resurrect instead of adding as new
        assert success is True
        assert was_resurrected is True
        mock_resurrect.assert_called_once_with(job_id, job_data)


def test_add_new_job_not_resurrected():
    """Test that truly new jobs are added normally, not resurrected."""
    
    # Setup mock database manager
    db_manager = MagicMock(spec=DatabaseManager)
    backend = DatabaseStorageBackend(db_manager)
    
    job_id = "550e8400-e29b-41d4-a716-446655440000"  # Valid UUID
    job_data = {
        'id': job_id,
        'company_name': 'Test Company',
        'title': 'Test Job',
        'url': 'https://example.com/job',
        'date_updated': 1234567890,
        'active': True,
        'locations': ['New York, NY'],
        'terms': ['Summer 2026'],
        'degrees': ["Bachelor's"]
    }
    
    # Mock session with no existing job
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    
    # Mock session_scope context manager
    db_manager.session_scope.return_value.__enter__.return_value = mock_session
    db_manager.session_scope.return_value.__exit__.return_value = None
    
    # Mock the job_posting_from_dict to avoid UUID issues
    with patch('chatd.storage_abstraction.job_posting_from_dict') as mock_from_dict:
        mock_job = MagicMock()
        mock_from_dict.return_value = mock_job
        
        # Mock the resurrect method (should not be called)
        with patch.object(backend, 'resurrect_job_posting') as mock_resurrect:
            # Try to add the job
            success, was_resurrected = backend.add_job_posting(job_data)
            
            # Should have added normally, not called resurrect
            assert success is True
            assert was_resurrected is False
            mock_resurrect.assert_not_called()
            # Should have called session.add with the new job
            mock_session.add.assert_called_once_with(mock_job)


def test_add_active_job_fails():
    """Test that attempting to add an already-active job fails correctly."""
    
    # Setup mock database manager
    db_manager = MagicMock(spec=DatabaseManager)
    backend = DatabaseStorageBackend(db_manager)
    
    job_id = "test-job-789"
    job_data = {
        'id': job_id,
        'company_name': 'Test Company',
        'title': 'Test Job',
        'url': 'https://example.com/job',
        'date_updated': 1234567890,
        'active': True,
        'locations': ['New York, NY'],
        'terms': ['Summer 2026'],
        'degrees': ["Bachelor's"]
    }
    
    # Mock an active (not soft-deleted) job
    mock_job = MagicMock(spec=JobPosting)
    mock_job.id = job_id
    mock_job.is_deleted = False
    
    # Mock session
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_job
    
    # Mock session_scope context manager
    db_manager.session_scope.return_value.__enter__.return_value = mock_session
    db_manager.session_scope.return_value.__exit__.return_value = None
    
    # Mock the resurrect method (should not be called)
    with patch.object(backend, 'resurrect_job_posting') as mock_resurrect:
        # Try to add the job
        success, was_resurrected = backend.add_job_posting(job_data)
        
        # Should fail - job already exists and is active
        assert success is False
        assert was_resurrected is False
        mock_resurrect.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
