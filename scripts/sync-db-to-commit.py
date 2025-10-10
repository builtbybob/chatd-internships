#!/usr/bin/env python3
"""
Sync PostgreSQL database to match a specific git commit.
This is useful for testing message replay functionality.

Usage:
    python sync-db-to-commit.py <commit-hash>
    python sync-db-to-commit.py HEAD~5  # Go back 5 commits
    python sync-db-to-commit.py --list-commits  # Show recent commits
"""

import argparse
import subprocess
import json
import os
import sys
import tempfile
from pathlib import Path

# Add the parent directory to the path so we can import chatd modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from chatd.config import Config

def run_git_command(cmd, repo_path):
    """Run a git command and return the output."""
    try:
        result = subprocess.run(
            cmd, 
            cwd=repo_path, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        print(f"Error output: {e.stderr}")
        return None

def get_listings_at_commit(commit_hash, repo_path):
    """Get the listings.json content at a specific commit."""
    cmd = ['git', 'show', f'{commit_hash}:.github/scripts/listings.json']
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Failed to get listings at commit {commit_hash}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON at commit {commit_hash}: {e}")
        return None

def sync_database_to_commit(commit_hash, repo_path):
    """
    Sync database to match a git commit using existing change detection logic.
    This preserves jobs and message tracking that existed at the target commit.
    """
    print(f"🔄 Syncing database to commit: {commit_hash}")
    
    # Get the target state from git
    target_jobs = get_listings_at_commit(commit_hash, repo_path)
    if target_jobs is None:
        print("❌ Failed to get listings data")
        return False
    
    print(f"� Found {len(target_jobs)} jobs at commit {commit_hash}")
    
    # Use existing change detection and processing logic
    try:
        from chatd.storage_abstraction import StorageManager
        storage = StorageManager()
        
        print("🔍 Detecting changes between current database and target commit...")
        results = storage.process_job_changes(target_jobs)
        
        print(f"✅ Database sync completed:")
        print(f"   - {results['added_count']} jobs added")
        print(f"   - {results['updated_count']} jobs updated") 
        print(f"   - {results['removed_count']} jobs removed")
        
        if results['removed_count'] > 0:
            print(f"💡 {results['removed_count']} recent jobs were removed (with their message tracking)")
            print("   Jobs that existed at the target commit were preserved")
        
        return results['success']
        
    except Exception as e:
        print(f"❌ Failed to sync database: {e}")
        return False

def list_recent_commits(repo_path, count=10):
    """List recent commits for reference."""
    cmd = ['git', 'log', '--oneline', f'-{count}']
    output = run_git_command(cmd, repo_path)
    if output:
        print("Recent commits:")
        for line in output.split('\n'):
            print(f"  {line}")

def main():
    parser = argparse.ArgumentParser(description='Sync database to a git commit')
    parser.add_argument('commit', nargs='?', help='Git commit hash or reference (e.g., HEAD~5)')
    parser.add_argument('--list-commits', action='store_true', help='List recent commits')
    parser.add_argument('--repo-path', help='Path to the git repository', 
                       default='/app/Summer2026-Internships')
    
    args = parser.parse_args()
    
    # Ensure we have the config loaded
    config = Config()
    
    if args.list_commits:
        list_recent_commits(args.repo_path)
        return
    
    if not args.commit:
        print("Error: Please specify a commit hash or use --list-commits")
        parser.print_help()
        return
    
    print(f"🔄 Syncing database to commit: {args.commit}")
    
    # Sync using existing change detection logic
    success = sync_database_to_commit(args.commit, args.repo_path)
    
    if success:
        print(f"✅ Database successfully synced to commit {args.commit}")
        print("� You can now update to the latest commit to trigger message replay")
        print("   - Recent jobs have been removed (preserving older jobs and their messages)")
        print("   - When the bot next checks for updates, it will detect and post the 'new' jobs")
    else:
        print("❌ Database sync failed")

if __name__ == '__main__':
    main()