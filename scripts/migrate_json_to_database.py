#!/usr/bin/env python3
"""
Phase 4: Historical Data Migration Script

This script migrates existing JSON data files to the PostgreSQL database,
providing data validation, integrity checks, backups, and progress tracking.
"""

import os
import sys
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Add the chatd module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chatd.config import config
from chatd.database import DatabaseManager, job_posting_from_dict, MessageTracking
from chatd.storage_abstraction import DataStorage, JsonStorageBackend

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Custom exception for migration-related errors."""
    pass


class DataMigrator:
    """Handles migration of JSON data to PostgreSQL database."""
    
    def __init__(self, json_data_path: str = None, json_messages_path: str = None):
        """Initialize the migrator with data paths."""
        # Use provided paths or fall back to config defaults
        self.json_data_path = json_data_path or config.data_file
        self.json_messages_path = json_messages_path or config.messages_file
        
        # Handle the actual production path
        if json_data_path and not os.path.exists(json_data_path):
            # Try the production path
            prod_data_path = "/var/lib/chatd/data/previous_data.json"
            if os.path.exists(prod_data_path):
                self.json_data_path = prod_data_path
                logger.info(f"Using production data file: {prod_data_path}")
        elif not json_data_path:
            # Default to production path if no path provided
            prod_data_path = "/var/lib/chatd/data/previous_data.json"
            if os.path.exists(prod_data_path):
                self.json_data_path = prod_data_path
                logger.info(f"Using production data file: {prod_data_path}")
            else:
                logger.info(f"Production data file not found, using config default: {self.json_data_path}")
        
        # Initialize database manager
        self.db_manager = None
        self.migration_stats = {
            'jobs_total': 0,
            'jobs_migrated': 0,
            'jobs_failed': 0,
            'messages_total': 0,
            'messages_migrated': 0,
            'messages_failed': 0,
            'start_time': None,
            'end_time': None
        }
        
    def connect_database(self) -> bool:
        """Establish database connection."""
        try:
            # Use localhost when running outside Docker
            db_host = 'localhost' if os.getenv('DOCKER_CONTAINER') != 'true' else config.db_host
            database_url = f"postgresql://{config.db_user}:{config.db_password}@{db_host}:{config.db_port}/{config.db_name}"
            
            logger.info(f"Connecting to database: postgresql://{config.db_user}:***@{db_host}:{config.db_port}/{config.db_name}")
            self.db_manager = DatabaseManager(database_url, echo=False)
            
            if self.db_manager.test_connection():
                logger.info("✅ Database connection successful")
                return True
            else:
                logger.error("❌ Database connection failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            return False
    
    def create_backup(self, source_path: str, backup_suffix: str = None) -> str:
        """Create timestamped backup of source file."""
        if not os.path.exists(source_path):
            logger.warning(f"Source file doesn't exist: {source_path}")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{backup_suffix}" if backup_suffix else ""
        backup_path = f"{source_path}.backup_{timestamp}{suffix}"
        
        try:
            shutil.copy2(source_path, backup_path)
            logger.info(f"✅ Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None
    
    def load_json_data(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """Load and validate JSON data from file."""
        if not os.path.exists(file_path):
            logger.warning(f"JSON file doesn't exist: {file_path}")
            return []
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                raise MigrationError(f"Expected list of job postings, got {type(data)}")
                
            logger.info(f"✅ Loaded {len(data)} records from {file_path}")
            return data
            
        except json.JSONDecodeError as e:
            raise MigrationError(f"Invalid JSON format in {file_path}: {e}")
        except Exception as e:
            raise MigrationError(f"Failed to load JSON data: {e}")
    
    def validate_job_data(self, job_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate individual job posting data."""
        errors = []
        required_fields = ['company_name', 'title', 'url']
        
        # Check required fields
        for field in required_fields:
            if field not in job_data or not job_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate data types and formats
        if 'locations' in job_data and not isinstance(job_data['locations'], list):
            errors.append("locations must be a list")
            
        if 'terms' in job_data and not isinstance(job_data['terms'], list):
            errors.append("terms must be a list")
            
        if 'active' in job_data and not isinstance(job_data['active'], bool):
            errors.append("active must be a boolean")
            
        if 'date_posted' in job_data:
            try:
                float(job_data['date_posted'])
            except (TypeError, ValueError):
                errors.append("date_posted must be a valid timestamp")
        
        return len(errors) == 0, errors
    
    def migrate_job_postings(self, job_data: List[Dict[str, Any]], dry_run: bool = False) -> bool:
        """Migrate job postings to database."""
        logger.info(f"🔄 Migrating {len(job_data)} job postings...")
        self.migration_stats['jobs_total'] = len(job_data)
        
        if dry_run:
            logger.info("DRY RUN: No actual database changes will be made")
        
        success_count = 0
        failed_count = 0
        
        try:
            for i, job in enumerate(job_data, 1):
                # Validate job data
                is_valid, validation_errors = self.validate_job_data(job)
                
                if not is_valid:
                    logger.error(f"❌ Job {i} validation failed: {validation_errors}")
                    failed_count += 1
                    continue
                
                if dry_run:
                    logger.info(f"✅ Job {i}/{len(job_data)}: {job.get('company_name')} - {job.get('title')} (DRY RUN)")
                    success_count += 1
                    continue
                
                try:
                    # Add required fields if missing
                    if 'id' not in job:
                        import uuid
                        job['id'] = str(uuid.uuid4())
                    
                    if 'date_updated' not in job:
                        job['date_updated'] = int(datetime.now().timestamp())
                    
                    if 'source' not in job:
                        job['source'] = 'JSON Migration'
                        
                    if 'is_visible' not in job:
                        job['is_visible'] = True
                    
                    # Convert to ORM object
                    job_posting = job_posting_from_dict(job)
                    
                    # Save to database
                    with self.db_manager.session_scope() as session:
                        # Check if job already exists (by URL)
                        existing_job = session.query(self.db_manager.JobPosting).filter_by(url=job['url']).first()
                        if existing_job:
                            logger.warning(f"⚠️  Job {i} already exists (URL: {job['url']}), skipping")
                            continue
                        
                        session.add(job_posting)
                        session.flush()  # Get the ID
                        
                    logger.info(f"✅ Job {i}/{len(job_data)}: {job.get('company_name')} - {job.get('title')}")
                    success_count += 1
                    
                    # Progress update every 10 jobs
                    if i % 10 == 0:
                        logger.info(f"Progress: {i}/{len(job_data)} jobs processed ({success_count} successful, {failed_count} failed)")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to migrate job {i}: {e}")
                    failed_count += 1
            
            self.migration_stats['jobs_migrated'] = success_count
            self.migration_stats['jobs_failed'] = failed_count
            
            logger.info(f"✅ Job migration completed: {success_count} successful, {failed_count} failed")
            return failed_count == 0
            
        except Exception as e:
            logger.error(f"❌ Job migration failed: {e}")
            return False
    
    def migrate_message_tracking(self, messages_data: Dict[str, Dict[str, Any]], dry_run: bool = False) -> bool:
        """Migrate message tracking data to database."""
        if not messages_data:
            logger.info("No message tracking data to migrate")
            return True
            
        logger.info(f"🔄 Migrating {len(messages_data)} message tracking entries...")
        self.migration_stats['messages_total'] = len(messages_data)
        
        success_count = 0
        failed_count = 0
        
        try:
            for job_id, message_info in messages_data.items():
                try:
                    # Validate message tracking data
                    if not isinstance(message_info, dict):
                        logger.error(f"❌ Invalid message data for job {job_id}")
                        failed_count += 1
                        continue
                    
                    if 'message_id' not in message_info or 'channel_id' not in message_info:
                        logger.error(f"❌ Missing message_id or channel_id for job {job_id}")
                        failed_count += 1
                        continue
                    
                    if dry_run:
                        logger.info(f"✅ Message tracking for job {job_id} (DRY RUN)")
                        success_count += 1
                        continue
                    
                    # Create message tracking entry
                    posted_at = datetime.fromtimestamp(message_info.get('posted_at', datetime.now().timestamp()))
                    
                    message_tracking = MessageTracking(
                        id=job_id,
                        message_id=message_info['message_id'],
                        channel_id=message_info['channel_id'],
                        posted_at=posted_at
                    )
                    
                    # Save to database
                    with self.db_manager.session_scope() as session:
                        # Check if entry already exists
                        existing_entry = session.query(MessageTracking).filter_by(id=job_id).first()
                        if existing_entry:
                            logger.warning(f"⚠️  Message tracking for job {job_id} already exists, skipping")
                            continue
                        
                        session.add(message_tracking)
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ Failed to migrate message tracking for job {job_id}: {e}")
                    failed_count += 1
            
            self.migration_stats['messages_migrated'] = success_count
            self.migration_stats['messages_failed'] = failed_count
            
            if dry_run:
                logger.info(f"✅ Message tracking migration dry run completed: {success_count} valid, {failed_count} invalid")
            else:
                logger.info(f"✅ Message tracking migration completed: {success_count} successful, {failed_count} failed")
            
            return failed_count == 0
            
        except Exception as e:
            logger.error(f"❌ Message tracking migration failed: {e}")
            return False
    
    def verify_migration(self) -> bool:
        """Verify migration completeness and accuracy."""
        logger.info("🔍 Verifying migration...")
        
        try:
            # Count database records
            with self.db_manager.session_scope() as session:
                db_jobs_count = session.query(self.db_manager.JobPosting).count()
                db_messages_count = session.query(MessageTracking).count()
            
            logger.info(f"Database contains: {db_jobs_count} jobs, {db_messages_count} message tracking entries")
            logger.info(f"Migration stats: {self.migration_stats['jobs_migrated']} jobs, {self.migration_stats['messages_migrated']} messages")
            
            # Verify counts match (accounting for existing data)
            if db_jobs_count >= self.migration_stats['jobs_migrated']:
                logger.info("✅ Job count verification passed")
                jobs_verified = True
            else:
                logger.error(f"❌ Job count mismatch: expected at least {self.migration_stats['jobs_migrated']}, got {db_jobs_count}")
                jobs_verified = False
            
            if db_messages_count >= self.migration_stats['messages_migrated']:
                logger.info("✅ Message tracking count verification passed")
                messages_verified = True
            else:
                logger.error(f"❌ Message tracking count mismatch: expected at least {self.migration_stats['messages_migrated']}, got {db_messages_count}")
                messages_verified = False
            
            return jobs_verified and messages_verified
            
        except Exception as e:
            logger.error(f"❌ Migration verification failed: {e}")
            return False
    
    def run_migration(self, dry_run: bool = False, create_backups: bool = True) -> bool:
        """Run the complete migration process."""
        self.migration_stats['start_time'] = datetime.now()
        
        logger.info("🚀 Starting Phase 4: Historical Data Migration")
        logger.info(f"Data file: {self.json_data_path}")
        logger.info(f"Messages file: {self.json_messages_path}")
        
        try:
            # Step 1: Connect to database
            if not self.connect_database():
                raise MigrationError("Failed to connect to database")
            
            # Step 2: Create backups
            if create_backups and not dry_run:
                self.create_backup(self.json_data_path, "pre_migration")
                if os.path.exists(self.json_messages_path):
                    self.create_backup(self.json_messages_path, "pre_migration")
            
            # Step 3: Load JSON data
            job_data = self.load_json_data(self.json_data_path)
            if not job_data:
                logger.warning("No job data found, skipping job migration")
            
            messages_data = {}
            if os.path.exists(self.json_messages_path):
                messages_raw = self.load_json_data(self.json_messages_path)
                if messages_raw and isinstance(messages_raw, dict):
                    messages_data = messages_raw
                elif messages_raw:
                    logger.warning("Message data is not in expected format, skipping message migration")
            
            # Step 4: Migrate job postings
            if job_data:
                if not self.migrate_job_postings(job_data, dry_run):
                    logger.error("Job migration had failures")
            
            # Step 5: Migrate message tracking
            if messages_data:
                if not self.migrate_message_tracking(messages_data, dry_run):
                    logger.error("Message tracking migration had failures")
            
            # Step 6: Verify migration (if not dry run)
            if not dry_run:
                if not self.verify_migration():
                    logger.error("Migration verification failed")
            
            self.migration_stats['end_time'] = datetime.now()
            duration = self.migration_stats['end_time'] - self.migration_stats['start_time']
            
            logger.info("🎉 Migration completed!")
            logger.info(f"Duration: {duration}")
            logger.info(f"Jobs: {self.migration_stats['jobs_migrated']}/{self.migration_stats['jobs_total']} migrated")
            logger.info(f"Messages: {self.migration_stats['messages_migrated']}/{self.migration_stats['messages_total']} migrated")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            self.migration_stats['end_time'] = datetime.now()
            return False


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(description='Migrate JSON data to PostgreSQL database')
    parser.add_argument('--data-file', help='Path to JSON data file (default: use config or /var/lib/chatd/data/previous_results.json)')
    parser.add_argument('--messages-file', help='Path to message tracking JSON file (default: use config)')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without making actual changes')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backup files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Use production path as default
    data_file = args.data_file or "/var/lib/chatd/data/previous_data.json"
    
    migrator = DataMigrator(
        json_data_path=data_file,
        json_messages_path=args.messages_file
    )
    
    success = migrator.run_migration(
        dry_run=args.dry_run,
        create_backups=not args.no_backup
    )
    
    if success:
        logger.info("✅ Phase 4 (Historical Data Migration) completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed")
        sys.exit(1)


if __name__ == '__main__':
    main()