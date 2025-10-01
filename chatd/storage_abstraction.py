"""
Storage abstraction layer for ChatD Internships Bot.

This module provides a unified interface for data storage that supports multiple backends:
- JSON file storage (legacy)
- PostgreSQL database storage (new)
- Dual-write mode (both simultaneously)

This enables seamless migration from JSON to database without downtime.
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pathlib import Path

from chatd.database import (
    DatabaseManager, JobPosting, JobLocation, JobTerm, JobDegree, MessageTracking,
    job_posting_from_dict, job_posting_to_dict, create_database_manager
)

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def get_job_postings(self) -> List[Dict[str, Any]]:
        """Get all job postings."""
        pass
    
    @abstractmethod
    def save_job_postings(self, job_postings: List[Dict[str, Any]]) -> bool:
        """Save job postings."""
        pass
    
    @abstractmethod
    def get_message_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Get message tracking data."""
        pass
    
    @abstractmethod
    def save_message_tracking(self, message_tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save message tracking data."""
        pass
    
    @abstractmethod
    def get_job_posting_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job posting by ID."""
        pass
    
    @abstractmethod
    def add_message_tracking(self, job_id: str, message_id: str, channel_id: str) -> bool:
        """Add message tracking for a job posting."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the storage backend is healthy."""
        pass
    
    @abstractmethod
    def detect_job_changes(self, current_jobs: List[Dict[str, Any]], previous_jobs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Detect changes between current and previous job postings.
        
        Args:
            current_jobs: New job postings data
            previous_jobs: Previous job postings data
            
        Returns:
            Dictionary with change detection results:
            {
                'added': [job_dict, ...],
                'updated': [{'job': job_dict, 'changes': {'field': {'old': val, 'new': val}}}, ...],
                'removed': [job_dict, ...]
            }
        """
        pass
    
    @abstractmethod
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of a job posting.
        
        Args:
            job_id: ID of the job posting to update
            updates: Dictionary of field updates {field_name: new_value}
            
        Returns:
            True if successful, False otherwise
        """
        pass


class JsonStorageBackend(StorageBackend):
    """JSON file storage backend (legacy)."""
    
    def __init__(self, data_file: str, messages_file: str):
        self.data_file = Path(data_file)
        self.messages_file = Path(messages_file)
        
        # Ensure parent directories exist
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.messages_file.parent.mkdir(parents=True, exist_ok=True)
    
    def get_job_postings(self) -> List[Dict[str, Any]]:
        """Get all job postings from JSON file."""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded {len(data)} job postings from JSON file")
                    return data
            else:
                logger.info("JSON data file does not exist, returning empty list")
                return []
        except Exception as e:
            logger.error(f"Failed to load job postings from JSON: {e}")
            return []
    
    def save_job_postings(self, job_postings: List[Dict[str, Any]]) -> bool:
        """Save job postings to JSON file."""
        try:
            # Skip save if data hasn't changed (optimization)
            if self.data_file.exists():
                try:
                    existing_data = self.get_job_postings()
                    if existing_data == job_postings:
                        logger.debug("Job postings data unchanged, skipping save")
                        return True
                except Exception as e:
                    logger.debug(f"Could not compare existing data: {e}")
            
            # Save new data (no backup creation)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(job_postings, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved {len(job_postings)} job postings to JSON file")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save job postings to JSON: {e}")
            return False
    
    def get_message_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Get message tracking data from JSON file."""
        try:
            if self.messages_file.exists():
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded {len(data)} message tracking entries from JSON file")
                    return data
            else:
                logger.info("JSON messages file does not exist, returning empty dict")
                return {}
        except Exception as e:
            logger.error(f"Failed to load message tracking from JSON: {e}")
            return {}
    
    def save_message_tracking(self, message_tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save message tracking data to JSON file."""
        try:
            # Skip save if data hasn't changed (optimization)
            if self.messages_file.exists():
                try:
                    existing_data = self.get_message_tracking()
                    if existing_data == message_tracking:
                        logger.debug("Message tracking data unchanged, skipping save")
                        return True
                except Exception as e:
                    logger.debug(f"Could not compare existing message tracking: {e}")
            
            # Save new data (no backup creation)
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                json.dump(message_tracking, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved {len(message_tracking)} message tracking entries to JSON file")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save message tracking to JSON: {e}")
            return False
    
    def get_job_posting_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job posting by ID from JSON file."""
        job_postings = self.get_job_postings()
        for job in job_postings:
            if job.get('id') == job_id:
                return job
        return None
    
    def add_message_tracking(self, job_id: str, message_id: str, channel_id: str) -> bool:
        """Add message tracking for a job posting in JSON file."""
        try:
            message_tracking = self.get_message_tracking()
            message_tracking[job_id] = {
                'message_id': message_id,
                'channel_id': channel_id,
                'posted_at': int(time.time())
            }
            return self.save_message_tracking(message_tracking)
        except Exception as e:
            logger.error(f"Failed to add message tracking to JSON: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if JSON file storage is healthy."""
        try:
            # Check if we can read files
            self.get_job_postings()
            self.get_message_tracking()
            
            # Check if we can write files
            test_file = self.data_file.parent / '.health_check'
            test_file.write_text('test')
            test_file.unlink()
            
            return True
        except Exception as e:
            logger.error(f"JSON storage health check failed: {e}")
            return False
    
    def detect_job_changes(self, current_jobs: List[Dict[str, Any]], previous_jobs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Detect changes between current and previous job postings."""
        # Create lookup dictionaries by job ID
        current_by_id = {job['id']: job for job in current_jobs}
        previous_by_id = {job['id']: job for job in previous_jobs}
        
        # Track changes
        changes = {
            'added': [],
            'updated': [],
            'removed': []
        }
        
        # Find added jobs
        for job_id, job in current_by_id.items():
            if job_id not in previous_by_id:
                changes['added'].append(job)
        
        # Find removed jobs
        for job_id, job in previous_by_id.items():
            if job_id not in current_by_id:
                changes['removed'].append(job)
        
        # Find updated jobs (focus on key fields)
        key_fields = ['active', 'is_visible', 'date_updated']
        for job_id, current_job in current_by_id.items():
            if job_id in previous_by_id:
                previous_job = previous_by_id[job_id]
                job_changes = {}
                
                # Check key fields for changes
                for field in key_fields:
                    current_value = current_job.get(field)
                    previous_value = previous_job.get(field)
                    if current_value != previous_value:
                        job_changes[field] = {
                            'old': previous_value,
                            'new': current_value
                        }
                
                # If date_updated changed, it indicates content was corrected, check all fields
                if 'date_updated' in job_changes:
                    all_fields = ['url', 'company_name', 'title', 'sponsorship', 'source', 
                                 'date_posted', 'company_url', 'locations', 'terms']
                    for field in all_fields:
                        current_value = current_job.get(field)
                        previous_value = previous_job.get(field)
                        if current_value != previous_value:
                            job_changes[field] = {
                                'old': previous_value,
                                'new': current_value
                            }
                
                if job_changes:
                    changes['updated'].append({
                        'job': current_job,
                        'changes': job_changes
                    })
        
        logger.debug(f"Change detection: {len(changes['added'])} added, "
                    f"{len(changes['updated'])} updated, {len(changes['removed'])} removed")
        
        return changes
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a job posting in JSON storage."""
        try:
            job_postings = self.get_job_postings()
            
            # Find the job to update
            job_found = False
            for job in job_postings:
                if job.get('id') == job_id:
                    # Apply updates
                    for field, value in updates.items():
                        job[field] = value
                    job_found = True
                    break
            
            if not job_found:
                logger.error(f"Job posting {job_id} not found for update")
                return False
            
            # Save updated data
            return self.save_job_postings(job_postings)
            
        except Exception as e:
            logger.error(f"Failed to update job posting {job_id} in JSON: {e}")
            return False


class DatabaseStorageBackend(StorageBackend):
    """PostgreSQL database storage backend."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def get_job_postings(self) -> List[Dict[str, Any]]:
        """Get all job postings from database."""
        try:
            with self.db_manager.session_scope() as session:
                job_postings = session.query(JobPosting).all()
                result = [job_posting_to_dict(job) for job in job_postings]
                logger.debug(f"Loaded {len(result)} job postings from database")
                return result
        except Exception as e:
            logger.error(f"Failed to load job postings from database: {e}")
            return []
    
    def save_job_postings(self, job_postings: List[Dict[str, Any]]) -> bool:
        """
        Save job postings to database - DEPRECATED for incremental operations.
        This method should only be used for initial bulk loading or migration.
        For normal operations, use add_job_posting, update_job_posting, remove_job_posting.
        """
        logger.warning("save_job_postings called - this should only be used for bulk migration")
        
        # If this is a small number of jobs, process them individually for safety
        if len(job_postings) <= 50:
            logger.info(f"Processing {len(job_postings)} jobs individually for safety")
            success = True
            for job_data in job_postings:
                if not self.add_job_posting(job_data):
                    success = False
            return success
        
        # For large bulk operations (migration), use the old approach
        try:
            with self.db_manager.session_scope() as session:
                logger.warning("Performing bulk database replacement - this deletes all existing data")
                
                # Clear existing data (only for bulk migration)
                session.query(MessageTracking).delete(synchronize_session=False)
                session.query(JobLocation).delete(synchronize_session=False) 
                session.query(JobTerm).delete(synchronize_session=False)
                session.query(JobDegree).delete(synchronize_session=False)
                session.query(JobPosting).delete(synchronize_session=False)
                session.flush()
                
                # Insert all job postings
                for job_data in job_postings:
                    job_posting = job_posting_from_dict(job_data)
                    session.add(job_posting)
                
                logger.warning(f"Bulk loaded {len(job_postings)} job postings to database")
                return True
                
        except Exception as e:
            logger.error(f"Failed to bulk load job postings to database: {e}")
            return False
    
    def add_job_posting(self, job_data: Dict[str, Any]) -> bool:
        """Add a single new job posting to database, or update if it already exists."""
        try:
            with self.db_manager.session_scope() as session:
                job_id = job_data['id']
                
                # Check if job already exists by ID
                existing_job = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if existing_job:
                    logger.debug(f"Job {job_id} already exists by ID, updating instead")
                    return self.update_job_posting(job_id, job_data)
                
                # Check if job exists by URL (unique constraint)
                job_url = job_data.get('url')
                if job_url:
                    existing_job_by_url = session.query(JobPosting).filter(JobPosting.url == job_url).first()
                    if existing_job_by_url:
                        logger.debug(f"Job with URL {job_url} already exists (ID: {existing_job_by_url.id}), updating instead")
                        # Update the existing job with the new ID and data
                        return self.update_job_posting(str(existing_job_by_url.id), job_data)
                
                # Truly new job - insert it
                job_posting = job_posting_from_dict(job_data)
                session.add(job_posting)
                logger.debug(f"Added new job posting {job_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add job posting {job_data.get('id', 'unknown')}: {e}")
            return False
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of an existing job posting in database."""
        try:
            with self.db_manager.session_scope() as session:
                # Get existing job
                existing_job = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if not existing_job:
                    logger.warning(f"Cannot update job {job_id}: not found in database")
                    return False
                
                # Check if this is a full job update (from add_job_posting) or partial update
                is_full_update = 'url' in updates and 'company_name' in updates
                
                if is_full_update:
                    # Full job replacement - update the ID if it's different
                    new_job_id = updates.get('id', job_id)
                    if str(new_job_id) != str(job_id):
                        # Remove old job completely and insert new one
                        session.query(JobLocation).filter(JobLocation.id == job_id).delete(synchronize_session=False)
                        session.query(JobTerm).filter(JobTerm.id == job_id).delete(synchronize_session=False)
                        session.query(JobDegree).filter(JobDegree.id == job_id).delete(synchronize_session=False)
                        session.query(MessageTracking).filter(MessageTracking.id == job_id).delete(synchronize_session=False)
                        session.delete(existing_job)
                        session.flush()
                        
                        # Insert new job
                        job_posting = job_posting_from_dict(updates)
                        session.add(job_posting)
                        logger.debug(f"Replaced job {job_id} with {new_job_id}")
                        return True
                
                # Update main job posting fields (excluding relationships)
                for field, value in updates.items():
                    if field not in ['id', 'locations', 'terms', 'degrees']:
                        if hasattr(existing_job, field):
                            setattr(existing_job, field, value)
                        else:
                            # Skip unknown fields silently - they might be new fields not yet in the database schema
                            logger.debug(f"Skipping unknown field '{field}' in job posting update")
                            continue
                
                # Handle locations update if provided
                if 'locations' in updates:
                    session.query(JobLocation).filter(JobLocation.id == job_id).delete(synchronize_session=False)
                    for location in updates['locations']:
                        job_location = JobLocation(id=job_id, location=location)
                        session.add(job_location)
                
                # Handle terms update if provided
                if 'terms' in updates:
                    session.query(JobTerm).filter(JobTerm.id == job_id).delete(synchronize_session=False)
                    for term in updates['terms']:
                        job_term = JobTerm(id=job_id, term=term)
                        session.add(job_term)
                
                # Handle degrees update if provided
                if 'degrees' in updates:
                    session.query(JobDegree).filter(JobDegree.id == job_id).delete(synchronize_session=False)
                    for degree in updates['degrees']:
                        job_degree = JobDegree(id=job_id, degree=degree)
                        session.add(job_degree)
                
                logger.debug(f"Updated job posting {job_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job posting {job_id}: {e}")
            return False
    
    def remove_job_posting(self, job_id: str) -> bool:
        """Remove a job posting from database."""
        try:
            with self.db_manager.session_scope() as session:
                # Remove related data first
                session.query(MessageTracking).filter(MessageTracking.id == job_id).delete(synchronize_session=False)
                session.query(JobLocation).filter(JobLocation.id == job_id).delete(synchronize_session=False)
                session.query(JobTerm).filter(JobTerm.id == job_id).delete(synchronize_session=False)
                session.query(JobDegree).filter(JobDegree.id == job_id).delete(synchronize_session=False)
                
                # Remove main job posting
                deleted_count = session.query(JobPosting).filter(JobPosting.id == job_id).delete(synchronize_session=False)
                
                if deleted_count > 0:
                    logger.debug(f"Removed job posting {job_id}")
                    return True
                else:
                    logger.warning(f"Job posting {job_id} not found for removal")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to remove job posting {job_id}: {e}")
            return False
    
    def get_message_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Get message tracking data from database."""
        try:
            with self.db_manager.session_scope() as session:
                tracking_entries = session.query(MessageTracking).all()
                result = {}
                
                for entry in tracking_entries:
                    result[str(entry.id)] = {
                        'message_id': entry.message_id,
                        'channel_id': entry.channel_id,
                        'posted_at': int(entry.posted_at.timestamp()) if entry.posted_at else int(time.time())
                    }
                
                logger.debug(f"Loaded {len(result)} message tracking entries from database")
                return result
                
        except Exception as e:
            logger.error(f"Failed to load message tracking from database: {e}")
            return {}
    
    def save_message_tracking(self, message_tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save message tracking data to database."""
        try:
            with self.db_manager.session_scope() as session:
                # Clear existing message tracking
                session.query(MessageTracking).delete()
                
                # Insert new message tracking
                for job_id, tracking_data in message_tracking.items():
                    try:
                        tracking_entry = MessageTracking(
                            id=job_id,
                            message_id=tracking_data['message_id'],
                            channel_id=tracking_data['channel_id'],
                            posted_at=datetime.fromtimestamp(tracking_data.get('posted_at', time.time()))
                        )
                        session.add(tracking_entry)
                    except Exception as e:
                        logger.warning(f"Failed to add message tracking for job {job_id}: {e}")
                
                logger.debug(f"Saved {len(message_tracking)} message tracking entries to database")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save message tracking to database: {e}")
            return False
    
    def get_job_posting_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job posting by ID from database."""
        try:
            with self.db_manager.session_scope() as session:
                job_posting = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if job_posting:
                    return job_posting_to_dict(job_posting)
                return None
        except Exception as e:
            logger.error(f"Failed to get job posting {job_id} from database: {e}")
            return None
    
    def add_message_tracking(self, job_id: str, message_id: str, channel_id: str) -> bool:
        """Add message tracking for a job posting in database."""
        try:
            with self.db_manager.session_scope() as session:
                # Check if job posting exists
                job_exists = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if not job_exists:
                    logger.error(f"Cannot add message tracking: job posting {job_id} does not exist")
                    return False
                
                # Add or update message tracking
                tracking_entry = session.query(MessageTracking).filter(MessageTracking.id == job_id).first()
                if tracking_entry:
                    tracking_entry.message_id = message_id
                    tracking_entry.channel_id = channel_id
                    tracking_entry.posted_at = datetime.now()
                else:
                    tracking_entry = MessageTracking(
                        id=job_id,
                        message_id=message_id,
                        channel_id=channel_id,
                        posted_at=datetime.now()
                    )
                    session.add(tracking_entry)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to add message tracking to database: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if database storage is healthy."""
        return self.db_manager.test_connection()
    
    def detect_job_changes(self, current_jobs: List[Dict[str, Any]], previous_jobs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Detect changes between current and previous job postings (database implementation)."""
        # Use the same logic as JSON backend for consistency
        current_by_id = {job['id']: job for job in current_jobs}
        previous_by_id = {job['id']: job for job in previous_jobs}
        
        changes = {
            'added': [],
            'updated': [],
            'removed': []
        }
        
        # Find added jobs
        for job_id, job in current_by_id.items():
            if job_id not in previous_by_id:
                changes['added'].append(job)
        
        # Find removed jobs
        for job_id, job in previous_by_id.items():
            if job_id not in current_by_id:
                changes['removed'].append(job)
        
        # Find updated jobs (focus on key fields)
        key_fields = ['active', 'is_visible', 'date_updated']
        for job_id, current_job in current_by_id.items():
            if job_id in previous_by_id:
                previous_job = previous_by_id[job_id]
                job_changes = {}
                
                # Check key fields for changes
                for field in key_fields:
                    current_value = current_job.get(field)
                    previous_value = previous_job.get(field)
                    if current_value != previous_value:
                        job_changes[field] = {
                            'old': previous_value,
                            'new': current_value
                        }
                
                # If date_updated changed, it indicates content was corrected, check all fields
                if 'date_updated' in job_changes:
                    all_fields = ['url', 'company_name', 'title', 'sponsorship', 'source', 
                                 'date_posted', 'company_url', 'locations', 'terms']
                    for field in all_fields:
                        current_value = current_job.get(field)
                        previous_value = previous_job.get(field)
                        if current_value != previous_value:
                            job_changes[field] = {
                                'old': previous_value,
                                'new': current_value
                            }
                
                if job_changes:
                    changes['updated'].append({
                        'job': current_job,
                        'changes': job_changes
                    })
        
        logger.debug(f"Database change detection: {len(changes['added'])} added, "
                    f"{len(changes['updated'])} updated, {len(changes['removed'])} removed")
        
        return changes
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a job posting in database."""
        try:
            with self.db_manager.session_scope() as session:
                # Find the job posting
                job_posting = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if not job_posting:
                    logger.error(f"Job posting {job_id} not found for update")
                    return False
                
                # Update the job posting fields
                for field, value in updates.items():
                    if field in ['locations', 'terms']:
                        # Handle relationship updates
                        if field == 'locations':
                            # Remove existing locations
                            session.query(JobLocation).filter(JobLocation.id == job_id).delete()
                            # Add new locations
                            for location in value:
                                job_location = JobLocation(id=job_id, location=location)
                                session.add(job_location)
                        elif field == 'terms':
                            # Remove existing terms
                            session.query(JobTerm).filter(JobTerm.id == job_id).delete()
                            # Add new terms
                            for term in value:
                                job_term = JobTerm(id=job_id, term=term)
                                session.add(job_term)
                    else:
                        # Handle scalar field updates
                        if hasattr(job_posting, field):
                            setattr(job_posting, field, value)
                        else:
                            logger.warning(f"Unknown field {field} in job posting update")
                
                logger.debug(f"Updated job posting {job_id} with fields: {list(updates.keys())}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job posting {job_id} in database: {e}")
            return False


class DataStorage:
    """
    Unified data storage interface supporting multiple backends and migration modes.
    
    Migration modes:
    - json_only: Use only JSON file storage (legacy mode)
    - dual_write: Write to both JSON and database, read from JSON (migration mode)
    - database_only: Use only database storage (target mode)
    """
    
    def __init__(self, config):
        self.config = config
        self.migration_mode = config.migration_mode.lower()
        
        # Initialize backends based on migration mode
        self.json_backend = None
        self.database_backend = None
        
        # Always initialize JSON backend (needed for dual_write and json_only)
        if self.migration_mode in ['json_only', 'dual_write']:
            self.json_backend = JsonStorageBackend(config.data_file, config.messages_file)
            logger.info("Initialized JSON storage backend")
        
        # Initialize database backend (needed for dual_write and database_only)
        if self.migration_mode in ['dual_write', 'database_only']:
            try:
                db_manager = create_database_manager(config)
                if db_manager.test_connection():
                    self.database_backend = DatabaseStorageBackend(db_manager)
                    logger.info("Initialized database storage backend")
                else:
                    logger.error("Database connection failed, falling back to JSON mode")
                    self.migration_mode = 'json_only'
                    if not self.json_backend:
                        self.json_backend = JsonStorageBackend(config.data_file, config.messages_file)
            except Exception as e:
                logger.error(f"Failed to initialize database backend: {e}")
                logger.error("Falling back to JSON mode")
                self.migration_mode = 'json_only'
                if not self.json_backend:
                    self.json_backend = JsonStorageBackend(config.data_file, config.messages_file)
        
        logger.info(f"Storage initialized in {self.migration_mode} mode")
    
    def get_job_postings(self) -> List[Dict[str, Any]]:
        """Get all job postings using the appropriate backend."""
        if self.migration_mode == 'database_only':
            return self.database_backend.get_job_postings()
        else:
            # json_only and dual_write both read from JSON
            return self.json_backend.get_job_postings()
    
    def save_job_postings(self, job_postings: List[Dict[str, Any]]) -> bool:
        """Save job postings using the appropriate backend(s)."""
        success = True
        
        if self.migration_mode in ['json_only', 'dual_write']:
            json_success = self.json_backend.save_job_postings(job_postings)
            if not json_success:
                logger.error("Failed to save job postings to JSON backend")
                success = False
            else:
                logger.debug("Successfully saved job postings to JSON backend")
        
        if self.migration_mode in ['dual_write', 'database_only']:
            db_success = self.database_backend.save_job_postings(job_postings)
            if not db_success:
                logger.error("Failed to save job postings to database backend")
                success = False
            else:
                logger.debug("Successfully saved job postings to database backend")
        
        return success
    
    def get_message_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Get message tracking data using the appropriate backend."""
        if self.migration_mode == 'database_only':
            return self.database_backend.get_message_tracking()
        else:
            # json_only and dual_write both read from JSON
            return self.json_backend.get_message_tracking()
    
    def save_message_tracking(self, message_tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save message tracking data using the appropriate backend(s)."""
        success = True
        
        if self.migration_mode in ['json_only', 'dual_write']:
            json_success = self.json_backend.save_message_tracking(message_tracking)
            if not json_success:
                logger.error("Failed to save message tracking to JSON backend")
                success = False
            else:
                logger.debug("Successfully saved message tracking to JSON backend")
        
        if self.migration_mode in ['dual_write', 'database_only']:
            db_success = self.database_backend.save_message_tracking(message_tracking)
            if not db_success:
                logger.error("Failed to save message tracking to database backend")
                success = False
            else:
                logger.debug("Successfully saved message tracking to database backend")
        
        return success
    
    def get_job_posting_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job posting by ID using the appropriate backend."""
        if self.migration_mode == 'database_only':
            return self.database_backend.get_job_posting_by_id(job_id)
        else:
            # json_only and dual_write both read from JSON
            return self.json_backend.get_job_posting_by_id(job_id)
    
    def add_message_tracking(self, job_id: str, message_id: str, channel_id: str) -> bool:
        """Add message tracking for a job posting using the appropriate backend(s)."""
        success = True
        
        if self.migration_mode in ['json_only', 'dual_write']:
            json_success = self.json_backend.add_message_tracking(job_id, message_id, channel_id)
            if not json_success:
                logger.error("Failed to add message tracking to JSON backend")
                success = False
            else:
                logger.debug("Successfully added message tracking to JSON backend")
        
        if self.migration_mode in ['dual_write', 'database_only']:
            db_success = self.database_backend.add_message_tracking(job_id, message_id, channel_id)
            if not db_success:
                logger.error("Failed to add message tracking to database backend")
                success = False
            else:
                logger.debug("Successfully added message tracking to database backend")
        
        return success
    
    def health_check(self) -> Dict[str, bool]:
        """Check the health of all active backends."""
        health = {}
        
        if self.migration_mode in ['json_only', 'dual_write']:
            health['json'] = self.json_backend.health_check()
        
        if self.migration_mode in ['dual_write', 'database_only']:
            health['database'] = self.database_backend.health_check()
        
        return health
    
    def get_backend_status(self) -> Dict[str, Any]:
        """Get detailed status information about backends."""
        status = {
            'migration_mode': self.migration_mode,
            'backends': {},
            'health': self.health_check()
        }
        
        if self.json_backend:
            status['backends']['json'] = {
                'type': 'JsonStorageBackend',
                'data_file': str(self.json_backend.data_file),
                'messages_file': str(self.json_backend.messages_file)
            }
        
        if self.database_backend:
            status['backends']['database'] = {
                'type': 'DatabaseStorageBackend',
                'connection': 'active' if self.database_backend.health_check() else 'failed'
            }
        
        return status
    
    def detect_job_changes(self, current_jobs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Detect changes between current job data and stored data.
        
        Args:
            current_jobs: New job postings data from repository
            
        Returns:
            Dictionary with change detection results
        """
        # Get previous job data from storage
        previous_jobs = self.get_job_postings()
        
        # Use the primary backend for change detection
        if self.migration_mode == 'database_only':
            return self.database_backend.detect_job_changes(current_jobs, previous_jobs)
        else:
            # json_only and dual_write both use JSON as primary
            return self.json_backend.detect_job_changes(current_jobs, previous_jobs)
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of a job posting using the appropriate backend(s).
        
        Args:
            job_id: ID of the job posting to update
            updates: Dictionary of field updates {field_name: new_value}
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        if self.migration_mode in ['json_only', 'dual_write']:
            json_success = self.json_backend.update_job_posting(job_id, updates)
            if not json_success:
                logger.error(f"Failed to update job posting {job_id} in JSON backend")
                success = False
            else:
                logger.debug(f"Successfully updated job posting {job_id} in JSON backend")
        
        if self.migration_mode in ['dual_write', 'database_only']:
            db_success = self.database_backend.update_job_posting(job_id, updates)
            if not db_success:
                logger.error(f"Failed to update job posting {job_id} in database backend")
                success = False
            else:
                logger.debug(f"Successfully updated job posting {job_id} in database backend")
        
        return success
    
    def process_job_changes(self, current_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process job changes with intelligent update handling.
        
        This method detects changes and applies updates efficiently:
        - active/is_visible changes: Update only those fields
        - date_updated changes: Update entire job posting (content correction)
        - Ensures idempotency and handles concurrent changes gracefully
        
        Args:
            current_jobs: New job postings data
            
        Returns:
            Dictionary with processing results and statistics
        """
        # Detect changes
        changes = self.detect_job_changes(current_jobs)
        
        results = {
            'added_count': len(changes['added']),
            'updated_count': len(changes['updated']),
            'removed_count': len(changes['removed']),
            'update_failures': [],
            'success': True,
            'changes_for_discord': changes  # Store change detection results for Discord processing
        }
        
        # Process updates efficiently
        for update_info in changes['updated']:
            job = update_info['job']
            job_changes = update_info['changes']
            job_id = job['id']
            
            try:
                # Determine update strategy based on changes
                if 'date_updated' in job_changes:
                    # Content correction: update entire job posting
                    logger.debug(f"Content correction detected for job {job_id}, updating entire posting")
                    if not self.update_job_posting(job_id, job):
                        results['update_failures'].append({'job_id': job_id, 'reason': 'full_update_failed'})
                        results['success'] = False
                else:
                    # Selective update: only changed fields
                    updates = {field: change_info['new'] for field, change_info in job_changes.items()}
                    logger.debug(f"Selective update for job {job_id}, fields: {list(updates.keys())}")
                    if not self.update_job_posting(job_id, updates):
                        results['update_failures'].append({'job_id': job_id, 'reason': 'selective_update_failed'})
                        results['success'] = False
                
            except Exception as e:
                logger.error(f"Failed to process updates for job {job_id}: {e}")
                results['update_failures'].append({'job_id': job_id, 'reason': str(e)})
                results['success'] = False
        
        # Handle new jobs (add them to storage)
        if changes['added']:
            try:
                # Handle JSON backend (bulk operation for efficiency)
                if self.migration_mode in ['json_only', 'dual_write']:
                    all_jobs = self.json_backend.get_job_postings()
                    all_jobs.extend(changes['added'])
                    if not self.json_backend.save_job_postings(all_jobs):
                        logger.error("Failed to add new jobs to JSON backend")
                        results['success'] = False
                
                # Handle database backend efficiently
                if self.migration_mode in ['dual_write', 'database_only']:
                    for job_data in changes['added']:
                        if not self.database_backend.add_job_posting(job_data):
                            logger.error(f"Failed to add job {job_data['id']} to database")
                            results['success'] = False

                logger.debug(f"Added {len(changes['added'])} new job postings")

            except Exception as e:
                logger.error(f"Failed to add new job postings: {e}")
                results['success'] = False
        
        # Handle removed jobs (remove from storage)
        if changes['removed']:
            try:
                removed_ids = {job['id'] for job in changes['removed']}
                
                # Remove from JSON backend if needed
                if self.migration_mode in ['json_only', 'dual_write']:
                    current_stored_jobs = self.json_backend.get_job_postings()
                    filtered_jobs = [job for job in current_stored_jobs if job['id'] not in removed_ids]
                    if not self.json_backend.save_job_postings(filtered_jobs):
                        logger.error("Failed to remove deleted job postings from JSON backend")
                        results['success'] = False
                
                # Remove from database backend efficiently
                if self.migration_mode in ['dual_write', 'database_only']:
                    for job_id in removed_ids:
                        if not self.database_backend.remove_job_posting(job_id):
                            logger.error(f"Failed to remove job {job_id} from database")
                            results['success'] = False
                
                if results['success']:
                    logger.info(f"Removed {len(changes['removed'])} deleted job postings")
                    
            except Exception as e:
                logger.error(f"Failed to remove deleted job postings: {e}")
                results['success'] = False
        
        logger.info(f"Change processing completed: {results['added_count']} added, "
                   f"{results['updated_count']} updated, {results['removed_count']} removed")
        
        return results