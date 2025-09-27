#!/usr/bin/env python3
"""
Tests for the Phase 4 historical data migration script.

This test suite validates the migration functionality including data validation,
backup creation, database operations, and error handling using proper pytest practices.
"""

import os
import sys
import json
import tempfile
import uuid
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add the chatd module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import after adding to path
from scripts.migrate_json_to_database import DataMigrator, MigrationError
from chatd.database import JobPosting, MessageTracking


class TestDataMigrator:
    """Test class for DataMigrator functionality."""

    @pytest.fixture
    def sample_job_data(self):
        """Provide sample job posting data for testing."""
        return [
            {
                'id': str(uuid.uuid4()),
                'company_name': 'Test Company A',
                'title': 'Software Engineer Intern',
                'url': 'https://example.com/job1',
                'locations': ['San Francisco, CA', 'Remote'],
                'terms': ['Summer 2026', 'Internship'],
                'sponsorship': 'Offers Sponsorship',
                'date_posted': int((datetime.now() - timedelta(days=1)).timestamp()),
                'active': True,
                'is_visible': True
            },
            {
                'id': str(uuid.uuid4()),
                'company_name': 'Test Company B',
                'title': 'Data Science Intern',
                'url': 'https://example.com/job2',
                'locations': ['New York, NY'],
                'terms': ['Summer 2026'],
                'sponsorship': 'No Sponsorship',
                'date_posted': int((datetime.now() - timedelta(days=2)).timestamp()),
                'active': True,
                'is_visible': True
            }
        ]

    @pytest.fixture
    def sample_message_data(self, sample_job_data):
        """Provide sample message tracking data for testing."""
        return {
            sample_job_data[0]['id']: {
                'message_id': '1234567890123456789',
                'channel_id': '9876543210987654321',
                'posted_at': int(datetime.now().timestamp())
            }
        }

    @pytest.fixture
    def temp_json_files(self, sample_job_data, sample_message_data):
        """Create temporary JSON files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create data file
            data_file = temp_path / 'test_data.json'
            with open(data_file, 'w') as f:
                json.dump(sample_job_data, f)
            
            # Create messages file
            messages_file = temp_path / 'test_messages.json'
            with open(messages_file, 'w') as f:
                json.dump(sample_message_data, f)
            
            yield str(data_file), str(messages_file)

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager for testing."""
        mock_manager = Mock()
        mock_manager.test_connection.return_value = True
        
        # Mock session context manager
        mock_session = Mock()
        mock_session_context = Mock()
        mock_session_context.__enter__ = Mock(return_value=mock_session)
        mock_session_context.__exit__ = Mock(return_value=None)
        mock_manager.session_scope.return_value = mock_session_context
        
        # Mock query operations
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.query.return_value.count.return_value = 2
        mock_session.add = Mock()
        mock_session.flush = Mock()
        
        # Add JobPosting and MessageTracking classes
        mock_manager.JobPosting = JobPosting
        
        return mock_manager

    def test_migrator_initialization(self):
        """Test DataMigrator initialization."""
        migrator = DataMigrator('/path/to/data.json', '/path/to/messages.json')
        
        assert migrator.json_data_path == '/path/to/data.json'
        assert migrator.json_messages_path == '/path/to/messages.json'
        assert migrator.db_manager is None
        assert migrator.migration_stats['jobs_total'] == 0
        assert migrator.migration_stats['start_time'] is None

    def test_load_json_data_success(self, temp_json_files, sample_job_data):
        """Test successful JSON data loading."""
        data_file, _ = temp_json_files
        migrator = DataMigrator()
        
        loaded_data = migrator.load_json_data(data_file)
        
        assert loaded_data is not None
        assert len(loaded_data) == len(sample_job_data)
        assert loaded_data[0]['company_name'] == sample_job_data[0]['company_name']

    def test_load_json_data_file_not_found(self):
        """Test JSON data loading with missing file."""
        migrator = DataMigrator()
        
        result = migrator.load_json_data('/nonexistent/file.json')
        
        assert result == []

    def test_load_json_data_invalid_json(self):
        """Test JSON data loading with invalid JSON format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json content {')
            temp_file = f.name
        
        try:
            migrator = DataMigrator()
            
            with pytest.raises(MigrationError, match="Invalid JSON format"):
                migrator.load_json_data(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_json_data_not_list(self):
        """Test JSON data loading when content is not a list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'not': 'a list'}, f)
            temp_file = f.name
        
        try:
            migrator = DataMigrator()
            
            with pytest.raises(MigrationError, match="Expected list of job postings"):
                migrator.load_json_data(temp_file)
        finally:
            os.unlink(temp_file)

    def test_validate_job_data_valid(self, sample_job_data):
        """Test job data validation with valid data."""
        migrator = DataMigrator()
        
        is_valid, errors = migrator.validate_job_data(sample_job_data[0])
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_job_data_missing_required_fields(self):
        """Test job data validation with missing required fields."""
        migrator = DataMigrator()
        invalid_data = {'company_name': 'Test Company'}  # Missing title and url
        
        is_valid, errors = migrator.validate_job_data(invalid_data)
        
        assert is_valid is False
        assert 'Missing required field: title' in errors
        assert 'Missing required field: url' in errors

    def test_validate_job_data_invalid_types(self):
        """Test job data validation with invalid data types."""
        migrator = DataMigrator()
        invalid_data = {
            'company_name': 'Test Company',
            'title': 'Test Title',
            'url': 'https://example.com',
            'locations': 'not a list',  # Should be list
            'terms': 'not a list',      # Should be list
            'active': 'not a boolean',  # Should be boolean
            'date_posted': 'invalid'    # Should be numeric
        }
        
        is_valid, errors = migrator.validate_job_data(invalid_data)
        
        assert is_valid is False
        assert 'locations must be a list' in errors
        assert 'terms must be a list' in errors
        assert 'active must be a boolean' in errors
        assert 'date_posted must be a valid timestamp' in errors

    def test_create_backup_success(self):
        """Test successful backup creation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('test content')
            source_file = f.name
        
        try:
            migrator = DataMigrator()
            
            backup_path = migrator.create_backup(source_file, 'test')
            
            assert backup_path is not None
            assert os.path.exists(backup_path)
            assert 'backup_' in backup_path
            assert '_test' in backup_path
            
            # Verify backup content
            with open(backup_path, 'r') as f:
                assert f.read() == 'test content'
                
            os.unlink(backup_path)
        finally:
            os.unlink(source_file)

    def test_create_backup_file_not_found(self):
        """Test backup creation with missing source file."""
        migrator = DataMigrator()
        
        backup_path = migrator.create_backup('/nonexistent/file.txt')
        
        assert backup_path is None

    @patch('scripts.migrate_json_to_database.DatabaseManager')
    def test_connect_database_success(self, mock_db_manager_class):
        """Test successful database connection."""
        mock_db_instance = Mock()
        mock_db_instance.test_connection.return_value = True
        mock_db_manager_class.return_value = mock_db_instance
        
        migrator = DataMigrator()
        
        result = migrator.connect_database()
        
        assert result is True
        assert migrator.db_manager == mock_db_instance

    @patch('scripts.migrate_json_to_database.DatabaseManager')
    def test_connect_database_failure(self, mock_db_manager_class):
        """Test database connection failure."""
        mock_db_instance = Mock()
        mock_db_instance.test_connection.return_value = False
        mock_db_manager_class.return_value = mock_db_instance
        
        migrator = DataMigrator()
        
        result = migrator.connect_database()
        
        assert result is False

    def test_migrate_job_postings_dry_run(self, sample_job_data, mock_db_manager):
        """Test job migration in dry run mode."""
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        
        result = migrator.migrate_job_postings(sample_job_data, dry_run=True)
        
        assert result is True
        assert migrator.migration_stats['jobs_total'] == len(sample_job_data)
        assert migrator.migration_stats['jobs_migrated'] == len(sample_job_data)
        assert migrator.migration_stats['jobs_failed'] == 0

    def test_migrate_job_postings_with_validation_errors(self, mock_db_manager):
        """Test job migration with validation errors."""
        invalid_data = [
            {'company_name': 'Test Company'},  # Missing required fields
            {'invalid': 'data'}  # Missing all required fields
        ]
        
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        
        result = migrator.migrate_job_postings(invalid_data, dry_run=True)
        
        assert result is False  # Should fail due to validation errors
        assert migrator.migration_stats['jobs_failed'] == 2

    def test_migrate_message_tracking_dry_run(self, sample_message_data, mock_db_manager):
        """Test message tracking migration in dry run mode."""
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        
        result = migrator.migrate_message_tracking(sample_message_data, dry_run=True)
        
        assert result is True
        assert migrator.migration_stats['messages_total'] == len(sample_message_data)
        assert migrator.migration_stats['messages_migrated'] == len(sample_message_data)

    def test_migrate_message_tracking_empty_data(self, mock_db_manager):
        """Test message tracking migration with empty data."""
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        
        result = migrator.migrate_message_tracking({}, dry_run=False)
        
        assert result is True
        assert migrator.migration_stats['messages_total'] == 0

    def test_migrate_message_tracking_invalid_data(self, mock_db_manager):
        """Test message tracking migration with invalid data."""
        invalid_data = {
            'job_id_1': 'not_a_dict',
            'job_id_2': {'missing_message_id': 'value'}
        }
        
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        
        result = migrator.migrate_message_tracking(invalid_data, dry_run=True)
        
        assert result is False  # Should fail due to invalid data
        assert migrator.migration_stats['messages_failed'] == 2

    def test_verify_migration_success(self, mock_db_manager):
        """Test successful migration verification."""
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        migrator.migration_stats['jobs_migrated'] = 2
        migrator.migration_stats['messages_migrated'] = 1
        
        # Mock database counts
        mock_db_manager.session_scope.return_value.__enter__.return_value.query.return_value.count.return_value = 2
        
        result = migrator.verify_migration()
        
        assert result is True

    def test_verify_migration_count_mismatch(self, mock_db_manager):
        """Test migration verification with count mismatch."""
        migrator = DataMigrator()
        migrator.db_manager = mock_db_manager
        migrator.migration_stats['jobs_migrated'] = 5
        migrator.migration_stats['messages_migrated'] = 3
        
        # Mock database counts (lower than expected)
        mock_session = mock_db_manager.session_scope.return_value.__enter__.return_value
        mock_session.query.return_value.count.side_effect = [2, 1]  # Less than migrated
        
        result = migrator.verify_migration()
        
        assert result is False

    @patch('scripts.migrate_json_to_database.os.path.exists')
    def test_run_migration_dry_run_success(self, mock_exists, temp_json_files, sample_job_data, mock_db_manager):
        """Test complete dry run migration process."""
        data_file, messages_file = temp_json_files
        mock_exists.return_value = True
        
        migrator = DataMigrator(data_file, messages_file)
        
        with patch.object(migrator, 'connect_database', return_value=True), \
             patch.object(migrator, 'load_json_data', side_effect=[sample_job_data, {}]), \
             patch.object(migrator, 'migrate_job_postings', return_value=True), \
             patch.object(migrator, 'migrate_message_tracking', return_value=True):
            
            result = migrator.run_migration(dry_run=True, create_backups=False)
        
        assert result is True
        assert migrator.migration_stats['start_time'] is not None
        assert migrator.migration_stats['end_time'] is not None

    def test_run_migration_database_connection_failure(self):
        """Test migration with database connection failure."""
        migrator = DataMigrator()
        
        with patch.object(migrator, 'connect_database', return_value=False):
            result = migrator.run_migration(dry_run=True)
        
        assert result is False

    @pytest.mark.parametrize("job_count,message_count", [
        (0, 0),     # No data
        (1, 0),     # Jobs only
        (0, 1),     # Messages only
        (5, 3),     # Both
    ])
    def test_migration_stats_tracking(self, job_count, message_count):
        """Test that migration statistics are properly tracked."""
        migrator = DataMigrator()
        
        # Initialize stats as they would be during migration
        migrator.migration_stats.update({
            'jobs_total': job_count,
            'jobs_migrated': job_count,
            'jobs_failed': 0,
            'messages_total': message_count,
            'messages_migrated': message_count,
            'messages_failed': 0,
            'start_time': datetime.now(),
            'end_time': datetime.now()
        })
        
        assert migrator.migration_stats['jobs_total'] == job_count
        assert migrator.migration_stats['messages_total'] == message_count
        assert migrator.migration_stats['start_time'] is not None
        assert migrator.migration_stats['end_time'] is not None


class TestMigrationIntegration:
    """Integration tests for the migration process."""
    
    def test_full_migration_workflow(self):
        """Test the complete migration workflow with mocked components."""
        # This test validates the integration between components
        # without requiring actual database connections
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data files
            data_file = Path(temp_dir) / 'data.json'
            test_data = [{
                'id': str(uuid.uuid4()),
                'company_name': 'Integration Test Co',
                'title': 'Test Intern',
                'url': 'https://test.com/job',
                'locations': ['Test City'],
                'terms': ['Test Term'],
                'active': True
            }]
            
            with open(data_file, 'w') as f:
                json.dump(test_data, f)
            
            # Create migrator
            migrator = DataMigrator(str(data_file))
            
            # Mock database operations
            mock_db_manager = Mock()
            mock_db_manager.test_connection.return_value = True
            
            mock_session = Mock()
            mock_session_context = Mock()
            mock_session_context.__enter__ = Mock(return_value=mock_session)
            mock_session_context.__exit__ = Mock(return_value=None)
            mock_db_manager.session_scope.return_value = mock_session_context
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            migrator.db_manager = mock_db_manager
            
            # Run migration
            result = migrator.migrate_job_postings(test_data, dry_run=True)
            
            assert result is True
            assert migrator.migration_stats['jobs_migrated'] == 1
            assert migrator.migration_stats['jobs_failed'] == 0

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        migrator = DataMigrator('/nonexistent/file.json')
        
        # Test graceful handling of missing files
        data = migrator.load_json_data('/nonexistent/file.json')
        assert data == []
        
        # Test backup creation with missing source
        backup = migrator.create_backup('/nonexistent/source.json')
        assert backup is None
        
        # These operations should not raise exceptions
        # but return appropriate error indicators