#!/usr/bin/env python3
"""
Test the database sync functionality by creating sample data.
This simulates what the sync script would do without needing git history.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the path so we can import chatd modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from chatd.config import Config
from chatd.storage_abstraction import StorageManager

def create_test_jobs():
    """Create sample job data for testing."""
    return [
        {
            "id": "test-job-1",
            "company": "Test Company A",
            "title": "Software Engineer Intern",
            "locations": ["Remote", "New York, NY"],
            "terms": ["Summer 2026"],
            "date_posted": "2024-10-01",
            "url": "https://example.com/job1"
        },
        {
            "id": "test-job-2", 
            "company": "Test Company B",
            "title": "Data Science Intern",
            "locations": ["San Francisco, CA"],
            "terms": ["Summer 2026"],
            "date_posted": "2024-10-02",
            "url": "https://example.com/job2"
        }
    ]

def test_sync_functionality():
    """Test the sync functionality with sample data."""
    print("🧪 Testing database sync functionality...")
    
    try:
        # Initialize storage
        config = Config()
        storage = StorageManager()
        
        # Create test jobs
        test_jobs = create_test_jobs()
        print(f"📋 Created {len(test_jobs)} test jobs")
        
        # Process the jobs using existing change detection logic
        print("🔍 Processing test jobs...")
        results = storage.process_job_changes(test_jobs)
        
        print(f"✅ Test completed:")
        print(f"   - {results['added_count']} jobs added")
        print(f"   - {results['updated_count']} jobs updated") 
        print(f"   - {results['removed_count']} jobs removed")
        
        if results['success']:
            print("✅ Database sync functionality is working correctly!")
            print("💡 The bot will now see these test jobs as 'new' and post them")
            print("   Run this script again to test removal detection")
        else:
            print("❌ Database sync test failed")
            
        return results['success']
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == '__main__':
    test_sync_functionality()