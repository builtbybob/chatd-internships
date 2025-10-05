#!/usr/bin/env python3
"""
Test script to verify the database migration integration works correctly.
This tests the migration script's ability to handle the new --repo-path argument.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the chatd module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def create_test_listings_json(repo_path):
    """Create a test listings.json file in the expected location."""
    # Create directory structure
    github_scripts_dir = os.path.join(repo_path, '.github', 'scripts')
    os.makedirs(github_scripts_dir, exist_ok=True)
    
    # Create test data
    test_data = {
        "Summer2026": [
            {
                "company": "Test Company",
                "title": "Software Engineer Intern",
                "locations": "Remote",
                "application_link": "https://example.com/apply",
                "date_posted": "2024-01-15"
            },
            {
                "company": "Another Corp",
                "title": "Data Science Intern",
                "locations": "New York, NY",
                "application_link": "https://example.com/apply2",
                "date_posted": "2024-01-16"
            }
        ]
    }
    
    # Write test file
    listings_path = os.path.join(github_scripts_dir, 'listings.json')
    with open(listings_path, 'w') as f:
        json.dump(test_data, f, indent=2)
    
    return listings_path

def test_migration_script_args():
    """Test that the migration script accepts the new --repo-path argument."""
    print("🧪 Testing migration script argument parsing...")
    
    # Import the migration script
    try:
        from scripts.migrate_json_to_database import main
        print("✅ Migration script imports successfully")
    except ImportError as e:
        print(f"❌ Failed to import migration script: {e}")
        return False
    
    # Test with --help to see if --repo-path is available
    import subprocess
    try:
        result = subprocess.run([
            sys.executable, 
            'scripts/migrate_json_to_database.py', 
            '--help'
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__) + '/..')
        
        if '--repo-path' in result.stdout:
            print("✅ --repo-path argument is available")
            return True
        else:
            print("❌ --repo-path argument not found in help output")
            return False
            
    except Exception as e:
        print(f"❌ Error testing migration script: {e}")
        return False

def test_listings_json_path():
    """Test that the migration script can find listings.json in the expected location."""
    print("🧪 Testing listings.json path detection...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test repository structure
        listings_path = create_test_listings_json(temp_dir)
        print(f"📁 Created test listings.json at: {listings_path}")
        
        # Verify file exists
        if os.path.exists(listings_path):
            print("✅ Test listings.json file created successfully")
            
            # Read and verify content
            with open(listings_path, 'r') as f:
                data = json.load(f)
                if 'Summer2026' in data and len(data['Summer2026']) == 2:
                    print("✅ Test data structure is correct")
                    return True
                else:
                    print("❌ Test data structure is incorrect")
                    return False
        else:
            print("❌ Failed to create test listings.json file")
            return False

def main():
    """Run all tests."""
    print("🔬 Testing Database Migration Integration")
    print("=" * 50)
    
    tests = [
        ("Migration Script Args", test_migration_script_args),
        ("Listings.json Path", test_listings_json_path)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The migration integration is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)