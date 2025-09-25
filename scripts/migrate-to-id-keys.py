#!/usr/bin/env python3
"""
Migration script to convert message_tracking.json from old composite keys to new ID-based keys.

This script:
1. Loads the current message tracking data (old format)
2. Loads the current listings to create a mapping from old keys to new IDs
3. Creates a new message tracking file with ID-based keys
4. Backs up the original file

Usage: python scripts/migrate-to-id-keys.py
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional


def normalize_old_role_key(role: Dict[str, Any]) -> str:
    """
    Create the OLD normalized key format for backward compatibility.
    This matches the previous get_role_id function's fallback behavior.
    """
    def norm(s: Optional[str]) -> str:
        return (s or "").strip().lower()

    company = norm(role.get('company_name'))
    title = norm(role.get('title'))
    date_posted = role.get('date_posted', 0)
    
    return f"{company}__{title}__{date_posted}"


def main():
    # File paths
    listings_file = '/var/lib/chatd/repo/.github/scripts/listings.json'
    tracking_file = '/var/lib/chatd/data/message_tracking.json'
    backup_file = f'{tracking_file}.backup.{int(datetime.now().timestamp())}'
    
    print("🔄 Starting migration from old keys to ID-based keys...")
    print()
    
    # Check if files exist
    if not os.path.exists(listings_file):
        print(f"❌ Listings file not found: {listings_file}")
        return False
        
    if not os.path.exists(tracking_file):
        print(f"ℹ️  No message tracking file found: {tracking_file}")
        print("✅ No migration needed")
        return True
    
    # Load data
    print("📂 Loading data files...")
    
    with open(listings_file, 'r') as f:
        listings = json.load(f)
    
    with open(tracking_file, 'r') as f:
        old_tracking = json.load(f)
    
    print(f"📊 Loaded {len(listings)} listings and {len(old_tracking)} tracked messages")
    
    # Create mapping from old keys to IDs
    print("🔍 Creating old key -> ID mapping...")
    old_key_to_id = {}
    
    for entry in listings:
        if 'id' in entry:
            old_key = normalize_old_role_key(entry)
            entry_id = entry['id']
            
            if old_key in old_key_to_id:
                print(f"⚠️  Duplicate old key found: {old_key}")
                print(f"   Existing ID: {old_key_to_id[old_key]}")
                print(f"   New ID: {entry_id}")
                # Keep the first one we found
            else:
                old_key_to_id[old_key] = entry_id
    
    print(f"🗺️  Created mapping for {len(old_key_to_id)} unique old keys")
    
    # Migrate tracking data
    print("🔄 Migrating message tracking data...")
    new_tracking = {}
    migration_stats = {
        'migrated': 0,
        'not_found': 0,
        'duplicates': 0
    }
    
    not_found_keys = []
    
    for old_key, message_info in old_tracking.items():
        if old_key in old_key_to_id:
            new_id = old_key_to_id[old_key]
            
            if new_id in new_tracking:
                # Merge message info if ID already exists
                existing_messages = new_tracking[new_id]
                new_messages = message_info if isinstance(message_info, list) else [message_info]
                
                # Avoid duplicates based on message_id
                existing_msg_ids = {msg.get('message_id') for msg in existing_messages if isinstance(msg, dict)}
                
                for msg in new_messages:
                    if isinstance(msg, dict) and msg.get('message_id') not in existing_msg_ids:
                        existing_messages.append(msg)
                
                migration_stats['duplicates'] += 1
            else:
                new_tracking[new_id] = message_info
                migration_stats['migrated'] += 1
        else:
            migration_stats['not_found'] += 1
            not_found_keys.append(old_key)
    
    # Display migration results
    print()
    print("📈 Migration Results:")
    print(f"   ✅ Successfully migrated: {migration_stats['migrated']}")
    print(f"   🔗 Merged duplicates: {migration_stats['duplicates']}")
    print(f"   ❌ Not found in listings: {migration_stats['not_found']}")
    print()
    
    if not_found_keys:
        print("❌ Keys not found in current listings (first 5):")
        for key in not_found_keys[:5]:
            print(f"   {key[:100]}...")
        if len(not_found_keys) > 5:
            print(f"   ... and {len(not_found_keys) - 5} more")
        print()
        
        print("🤔 This could happen if:")
        print("   • Roles were removed from the repository")
        print("   • Role data was modified significantly")
        print("   • The old key generation had different logic")
        print()
    
    # Backup original file
    print(f"💾 Creating backup: {backup_file}")
    shutil.copy2(tracking_file, backup_file)
    
    # Write new tracking file
    print(f"💾 Writing migrated data to: {tracking_file}")
    with open(tracking_file, 'w') as f:
        json.dump(new_tracking, f, indent=2)
    
    print()
    print("✅ Migration completed successfully!")
    print(f"📊 Final tracking entries: {len(new_tracking)}")
    print(f"🔒 Backup saved as: {backup_file}")
    print()
    print("🔄 You can now deploy the updated bot code that uses ID-based keys")
    
    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)