"""
Comprehensive mock for DataStorage class that can be used across all tests.

This mock includes all methods from the real DataStorage class to prevent
AttributeError exceptions in tests.
"""

from typing import Dict, List, Any, Optional
from unittest.mock import Mock


class MockDataStorage:
    """
    Mock DataStorage class with all methods from the real DataStorage class.
    
    This class provides default implementations for all DataStorage methods,
    making it suitable for use in any test that patches DataStorage.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize mock storage with default data structures."""
        self.job_postings = []
        self.message_tracking = {}
        self.migration_mode = 'json_only'
        
    def get_job_postings(self) -> List[Dict[str, Any]]:
        """Mock implementation of get_job_postings."""
        return self.job_postings
    
    def save_job_postings(self, job_postings: List[Dict[str, Any]]) -> bool:
        """Mock implementation of save_job_postings."""
        self.job_postings = job_postings.copy()
        return True
    
    def get_message_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Mock implementation of get_message_tracking."""
        return self.message_tracking
    
    def save_message_tracking(self, message_tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Mock implementation of save_message_tracking."""
        self.message_tracking = message_tracking.copy()
        return True
    
    def get_job_posting_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Mock implementation of get_job_posting_by_id."""
        for job in self.job_postings:
            if job.get('id') == job_id:
                return job
        return None
    
    def add_message_tracking(self, job_id: str, message_id: str, channel_id: str) -> bool:
        """Mock implementation of add_message_tracking."""
        self.message_tracking[job_id] = {
            'message_id': message_id,
            'channel_id': channel_id,
            'posted_at': 1234567890
        }
        return True
    
    def health_check(self) -> Dict[str, bool]:
        """Mock implementation of health_check."""
        return {'json': True, 'database': True}
    
    def get_backend_status(self) -> Dict[str, Any]:
        """Mock implementation of get_backend_status."""
        return {
            'migration_mode': self.migration_mode,
            'backends': {'json': {'type': 'MockJsonBackend'}},
            'health': self.health_check()
        }
    
    def detect_job_changes(self, current_jobs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Mock implementation of detect_job_changes."""
        stored_ids = {job['id'] for job in self.job_postings}
        current_ids = {job['id'] for job in current_jobs}
        
        added = [job for job in current_jobs if job['id'] not in stored_ids]
        removed = [job for job in self.job_postings if job['id'] not in current_ids]
        
        # Detect updates by comparing jobs with same ID
        updated = []
        stored_jobs_by_id = {job['id']: job for job in self.job_postings}
        
        for current_job in current_jobs:
            job_id = current_job['id']
            if job_id in stored_jobs_by_id:
                stored_job = stored_jobs_by_id[job_id]
                # Check if any values have changed (simple comparison)
                if current_job != stored_job:
                    updated.append(current_job)
        
        return {
            'added': added,
            'updated': updated,
            'removed': removed
        }
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Mock implementation of update_job_posting."""
        for job in self.job_postings:
            if job.get('id') == job_id:
                job.update(updates)
                return True
        return False
    
    def process_job_changes(self, current_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Mock implementation of process_job_changes."""
        changes = self.detect_job_changes(current_jobs)
        
        # Update stored jobs to match current
        self.job_postings = current_jobs.copy()
        
        return {
            'added_count': len(changes['added']),
            'updated_count': len(changes['updated']),
            'removed_count': len(changes['removed']),
            'update_failures': [],
            'success': True,
            'changes_for_discord': changes
        }
    
    def update_job_posting_with_refresh(self, job: Dict[str, Any]) -> bool:
        """Mock implementation of update_job_posting_with_refresh."""
        job_id = job['id']
        for i, stored_job in enumerate(self.job_postings):
            if stored_job.get('id') == job_id:
                self.job_postings[i] = job.copy()
                return True
        return False
    
    # Additional helper methods for database backend compatibility
    def get_company_jobs_from_database(self, company_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """Mock implementation of get_company_jobs_from_database."""
        return [job for job in self.job_postings 
                if job.get('company_name', '').lower() == company_name.lower()]
    
    # Properties and attributes that might be accessed
    @property
    def database_backend(self):
        """Mock database_backend property."""
        # Return a mock object that has the get_company_jobs_from_database method
        mock_backend = Mock()
        mock_backend.get_company_jobs_from_database.return_value = []
        return mock_backend
    
    @property
    def json_backend(self):
        """Mock json_backend property."""
        mock_backend = Mock()
        mock_backend.get_job_postings.return_value = self.job_postings
        mock_backend.save_job_postings.return_value = True
        return mock_backend


def setup_mock_datastorage():
    """
    Setup function to replace DataStorage with MockDataStorage in imports.
    
    This function can be called at the beginning of test modules to ensure
    MockDataStorage is used instead of the real DataStorage class.
    """
    import sys
    
    # Create a comprehensive mock for DataStorage 
    if 'chatd.storage_abstraction' in sys.modules:
        storage_module = sys.modules['chatd.storage_abstraction']
        storage_module.DataStorage = MockDataStorage
    else:
        # Patch before import
        import chatd.storage_abstraction
        chatd.storage_abstraction.DataStorage = MockDataStorage


def create_mock_config():
    """
    Create a comprehensive mock config object for tests.
    
    This includes all configuration values that might be accessed by
    various parts of the codebase.
    """
    config = Mock()
    
    # Basic Discord configuration
    config.discord_token = 'test-token'
    config.channel_ids = ['123456789']
    config.enable_reactions = True
    config.enable_company_info = True
    config.info_reaction_emoji = '❓'
    
    # Performance configuration (Section 4.1)
    config.message_post_delay = 0.1
    config.reaction_delay = 0.5
    config.batch_processing_delay = 0.05
    config.max_retries = 3
    
    # Reaction batching configuration (Section 4.3)
    config.reaction_batch_size = 3
    config.reaction_batch_delay = 0.1
    config.reaction_retry_count = 2
    config.reaction_retry_delay = 0.05
    
    # Health monitoring configuration (Section 4.4)
    config.health_window_size = 100
    config.degradation_threshold = 0.5
    config.recovery_threshold = 0.2
    config.circuit_breaker_threshold = 10
    config.circuit_breaker_timeout = 300
    config.health_check_interval = 60
    
    # Company info configuration (Section 5)
    config.company_info_days = 7
    config.max_company_jobs_in_dm = 10
    
    # Data configuration
    config.max_post_age_days = 5
    config.migration_mode = 'json_only'
    config.data_file = '/tmp/test_data.json'
    config.messages_file = '/tmp/test_messages.json'
    
    # Database configuration
    config.db_type = 'postgresql'
    config.db_host = 'localhost'
    config.db_port = 5432
    config.db_name = 'test_db'
    config.db_user = 'test_user'
    config.db_password = 'test_password'
    config.db_connection_pool_size = 5
    
    return config