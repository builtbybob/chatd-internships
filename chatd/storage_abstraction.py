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
import uuid
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from pathlib import Path

from chatd.database import (
    DatabaseManager, JobPosting, JobLocation, JobTerm, JobDegree, MessageTracking, StudentApplication,
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
        key_fields = ['active', 'is_visible', 'is_deleted', 'date_updated']
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
    
    def get_job_postings(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get all job postings from database, excluding soft-deleted by default."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(JobPosting)
                
                # Filter out soft-deleted records by default
                if not include_deleted:
                    query = query.filter(JobPosting.is_deleted == False)
                
                job_postings = query.all()
                result = [job_posting_to_dict(job) for job in job_postings]
                logger.info(f"DatabaseStorageBackend.get_job_postings() loaded {len(result)} job postings from database (include_deleted={include_deleted})")
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
        """Add a single new job posting to database. Job must not already exist."""
        try:
            job_id = job_data['id']
            
            with self.db_manager.session_scope() as session:
                # Check if job already exists by ID
                existing_job = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if existing_job:
                    logger.warning(f"Job {job_id} already exists, cannot add as new. Use update methods instead.")
                    return False
                
                # Add the new job
                job_posting = job_posting_from_dict(job_data)
                session.add(job_posting)
                logger.debug(f"Added new job posting {job_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add job posting {job_data.get('id', 'unknown')}: {e}")
            return False
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of an existing job posting in database.
        
        This method is primarily used by add_job_posting for ID replacement cases.
        For regular updates, use update_job_posting_scalars (scalar fields only) or
        update_job_posting_with_refresh (content corrections with relationships).
        """
        try:
            with self.db_manager.session_scope() as session:
                # Get existing job
                existing_job = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if not existing_job:
                    logger.warning(f"Cannot update job {job_id}: not found in database")
                    return False
                
                # For partial updates, delegate to appropriate specialized methods
                has_relationships = any(field in updates for field in ['locations', 'terms', 'degrees'])
                
                if has_relationships:
                    logger.warning(f"Relationship fields detected in partial update for job {job_id}. "
                                 f"Use update_job_posting_with_refresh for content corrections or "
                                 f"update_job_posting_scalars for scalar-only updates.")
                    return False
                
                # Handle scalar fields only
                scalar_updates = {k: v for k, v in updates.items() if k not in ['id', 'locations', 'terms', 'degrees']}
                
                for field, value in scalar_updates.items():
                    if hasattr(existing_job, field):
                        setattr(existing_job, field, value)
                    else:
                        logger.debug(f"Skipping unknown field '{field}' in job posting update")
                
                logger.debug(f"Updated job posting {job_id} scalar fields: {list(scalar_updates.keys())}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job posting {job_id}: {e}")
            return False
    
    def remove_job_posting(self, job_id: str) -> bool:
        """Soft delete a job posting from database."""
        try:
            with self.db_manager.session_scope() as session:
                # Use soft delete: set is_deleted = True instead of hard deleting
                job_posting = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                
                if job_posting:
                    job_posting.is_deleted = True
                    logger.debug(f"Soft deleted job posting {job_id}")
                else:
                    logger.warning(f"Job posting {job_id} not found for soft deletion")
                
                # Return True in both cases - idempotent operation
                # Goal achieved: job posting is marked as deleted
                return True
                
        except Exception as e:
            logger.error(f"Failed to soft delete job posting {job_id}: {e}")
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
        key_fields = ['active', 'is_visible', 'is_deleted', 'date_updated']
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
    
    def update_job_posting_scalars(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update only scalar fields of a job posting in database (no relationship updates)."""
        try:
            with self.db_manager.session_scope() as session:
                # Find the job posting
                job_posting = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if not job_posting:
                    logger.error(f"Job posting {job_id} not found for scalar update. Updates were: {updates}")
                    # Check if this is a soft-deleted job
                    soft_deleted_job = session.query(JobPosting).filter(
                        JobPosting.id == job_id, 
                        JobPosting.is_deleted == True
                    ).first()
                    if soft_deleted_job:
                        logger.error(f"Job {job_id} is soft-deleted but scalar update attempted")
                    return False
                
                # Update only scalar fields
                scalar_updates = {}
                for field, value in updates.items():
                    if field in ['locations', 'terms', 'degrees']:
                        # Warn about relationship fields but don't process them
                        logger.warning(f"Ignoring relationship field '{field}' in scalar update for job {job_id}. Use content correction workflow for relationship updates.")
                        continue
                    elif field == 'id':
                        # Skip ID field
                        logger.debug(f"Skipping ID field in scalar update for job {job_id}")
                        continue
                    else:
                        # Handle scalar field updates
                        if hasattr(job_posting, field):
                            setattr(job_posting, field, value)
                            scalar_updates[field] = value
                        else:
                            logger.warning(f"Unknown field '{field}' in job posting scalar update")
                
                if scalar_updates:
                    logger.debug(f"Updated job posting {job_id} scalar fields: {list(scalar_updates.keys())}")
                else:
                    logger.debug(f"No scalar fields to update for job posting {job_id}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job posting {job_id} scalar fields: {e}")
            return False
    
    def add_student_application(self, job_id: str, discord_user_id: str) -> bool:
        """
        Add a student application record to the database.
        
        Args:
            job_id: UUID of the job posting
            discord_user_id: Discord user ID of the student
            
        Returns:
            bool: True if successful, False otherwise
        """
        from chatd.database import StudentApplication
        
        try:
            with self.db_manager.session_scope() as session:
                # Check if job posting exists and is not soft-deleted
                job_posting = session.query(JobPosting).filter(
                    JobPosting.id == job_id,
                    JobPosting.is_deleted == False
                ).first()
                
                if not job_posting:
                    logger.warning(f"Cannot add application: job {job_id} not found or is deleted")
                    return False
                
                # Check if application already exists (handle duplicate prevention)
                existing_application = session.query(StudentApplication).filter(
                    StudentApplication.job_id == job_id,
                    StudentApplication.discord_user_id == discord_user_id
                ).first()
                
                if existing_application:
                    logger.info(f"Application already exists for user {discord_user_id} on job {job_id}")
                    return False  # Duplicate - don't send another DM
                
                # Create new application record
                application = StudentApplication(
                    job_id=uuid.UUID(job_id),
                    discord_user_id=discord_user_id
                )
                
                session.add(application)
                session.commit()
                
                logger.info(f"Successfully added application for user {discord_user_id} on job {job_id}")
                return True
                
        except Exception as e:
            # Enhanced error logging with classification
            if "duplicate key value" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.info(f"Duplicate application attempt for user {discord_user_id} on job {job_id} - no DM needed")
                return False  # Duplicate - don't send DM
            elif "foreign key constraint" in str(e).lower():
                logger.warning(f"Job {job_id} not found for application by user {discord_user_id}")
                return False
            else:
                logger.error(f"Database error adding application for user {discord_user_id} on job {job_id}: {e}")
                return False
    
    def get_student_application_stats(self, discord_user_id: str) -> Dict[str, Any]:
        """
        Get student application statistics for congratulatory DMs.
        
        Args:
            discord_user_id: Discord user ID of the student
            
        Returns:
            Dictionary with application statistics
        """
        from chatd.database import StudentApplication
        from chatd.config import config
        
        try:
            with self.db_manager.session_scope() as session:
                # Get total application count
                total_applications = session.query(StudentApplication).filter(
                    StudentApplication.discord_user_id == discord_user_id
                ).count()
                
                # Get recent applications with job details (excluding soft-deleted jobs)
                recent_applications_query = session.query(
                    StudentApplication, JobPosting
                ).join(
                    JobPosting, StudentApplication.job_id == JobPosting.id
                ).filter(
                    StudentApplication.discord_user_id == discord_user_id,
                    JobPosting.is_deleted == False
                ).order_by(
                    StudentApplication.applied_at.desc()
                ).limit(config.max_recent_applications_shown)
                
                recent_applications = []
                for app, job in recent_applications_query:
                    recent_applications.append({
                        'company_name': job.company_name,
                        'title': job.title,
                        'url': job.url,
                        'applied_at': app.applied_at.isoformat(),
                        'job_id': str(app.job_id)
                    })
                
                return {
                    'total_applications': total_applications,
                    'recent_applications': recent_applications
                }
                
        except Exception as e:
            logger.error(f"Database error getting application stats for user {discord_user_id}: {e}")
            # Return safe defaults when database is unavailable
            return {'total_applications': 0, 'recent_applications': []}


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
            result = self.database_backend.get_job_postings()
            logger.info(f"DataStorage.get_job_postings() in database_only mode returned {len(result)} jobs")
            return result
        else:
            # json_only and dual_write both read from JSON
            result = self.json_backend.get_job_postings()
            logger.info(f"DataStorage.get_job_postings() in {self.migration_mode} mode returned {len(result)} jobs")
            return result
    
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
        
        # DEBUG: Log what we're comparing
        logger.info(f"Change detection: {len(current_jobs)} current jobs vs {len(previous_jobs)} previous jobs")
        if len(previous_jobs) == 0 and len(current_jobs) > 0:
            logger.error("CRITICAL: No previous jobs found from storage! All jobs will be treated as new.")
            logger.error("SAFETY: Aborting change detection to prevent duplicate insertion attempts")
            return {
                'changes': {
                    'added': [],
                    'updated': [],
                    'removed': []
                }
            }
        elif len(current_jobs) > 0 and len(previous_jobs) > 0:
            logger.debug(f"Sample current job ID: {current_jobs[0].get('id')} vs sample previous job ID: {previous_jobs[0].get('id')}")
        
        # Use the primary backend for change detection
        if self.migration_mode == 'database_only':
            return self.database_backend.detect_job_changes(current_jobs, previous_jobs)
        else:
            # json_only and dual_write both use JSON as primary
            return self.json_backend.detect_job_changes(current_jobs, previous_jobs)
    
    def update_job_posting(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific scalar fields of a job posting using the appropriate backend(s).
        
        Note: This method only handles scalar field updates. For relationship updates
        (locations, terms, degrees), use the content correction workflow via 
        process_job_changes when date_updated changes.
        
        Args:
            job_id: ID of the job posting to update
            updates: Dictionary of scalar field updates {field_name: new_value}
            
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
            db_success = self.database_backend.update_job_posting_scalars(job_id, updates)
            if not db_success:
                logger.error(f"Failed to update job posting {job_id} scalar fields in database backend")
                success = False
            else:
                logger.debug(f"Successfully updated job posting {job_id} scalar fields in database backend")
        
        return success
    
    def process_job_changes(self, current_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process job changes with intelligent update handling.
        
        This method detects changes and applies updates efficiently:
        - active/is_visible/is_deleted changes: Update only those fields
        - date_updated changes: Update entire job posting (content correction)
        - Ensures idempotency and handles concurrent changes gracefully
        
        Args:
            current_jobs: New job postings data
            
        Returns:
            Dictionary with processing results and statistics
        """
        # Normalize JSON data: if a job exists in the source file, it's not deleted
        normalized_jobs = []
        for job in current_jobs:
            normalized_job = job.copy()
            # Jobs present in JSON are by definition not deleted
            if 'is_deleted' not in normalized_job:
                normalized_job['is_deleted'] = False
            normalized_jobs.append(normalized_job)
        
        # Detect changes
        changes = self.detect_job_changes(normalized_jobs)
        
        results = {
            'added_count': len(changes['added']),
            'updated_count': len(changes['updated']),
            'removed_count': len(changes['removed']),
            'update_failures': [],
            'success': True,
            'changes_for_discord': changes  # Store change detection results for Discord processing
        }
        
        # Process updates efficiently with proper workflow separation
        for update_info in changes['updated']:
            job = update_info['job']
            job_changes = update_info['changes']
            job_id = job['id']
            
            try:
                # Determine update strategy: content corrections take priority
                if 'date_updated' in job_changes:
                    # Content correction workflow: full job refresh with relationships
                    logger.info(f"Content correction detected for job {job_id} (date_updated changed), using full refresh workflow")
                    
                    # For JSON backend, use the existing remove/add approach (no cascade delete issues)
                    if self.migration_mode in ['json_only', 'dual_write']:
                        current_jobs_stored = self.json_backend.get_job_postings()
                        filtered_jobs = [j for j in current_jobs_stored if j['id'] != job_id]
                        filtered_jobs.append(job)
                        if not self.json_backend.save_job_postings(filtered_jobs):
                            results['update_failures'].append({'job_id': job_id, 'reason': 'json_refresh_failed'})
                            results['success'] = False
                            continue
                    
                    # For database backend, use differential update to preserve message tracking
                    if self.migration_mode in ['dual_write', 'database_only']:
                        if not self.update_job_posting_with_refresh(job):
                            results['update_failures'].append({'job_id': job_id, 'reason': 'database_refresh_failed'})
                            results['success'] = False
                            continue
                    
                    logger.info(f"Successfully processed content correction for job posting {job_id}")
                else:
                    # Selective update workflow: only scalar fields changed (active, is_visible, is_deleted, etc.)
                    # Only process scalar fields - relationships are handled by content correction workflow
                    scalar_updates = {field: change_info['new'] for field, change_info in job_changes.items() 
                                    if field not in ['locations', 'terms', 'degrees']}
                    
                    if scalar_updates:
                        logger.debug(f"Selective scalar update for job {job_id}, fields: {list(scalar_updates.keys())}")
                        if not self.update_job_posting(job_id, scalar_updates):
                            results['update_failures'].append({'job_id': job_id, 'reason': 'selective_update_failed'})
                            results['success'] = False
                    else:
                        logger.debug(f"No scalar fields to update for job {job_id} (only relationship changes detected)")
                
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
    
    # Application tracking methods (Sections 5.8-5.12)
    
    def add_student_application(self, job_id: str, discord_user_id: str) -> bool:
        """
        Add a student application record.
        
        Args:
            job_id: UUID of the job posting
            discord_user_id: Discord user ID of the student
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Only support application tracking in database mode
        if self.migration_mode not in ['dual_write', 'database_only']:
            logger.warning("Application tracking requires database mode")
            return False
            
        return self.database_backend.add_student_application(job_id, discord_user_id)
    
    def get_student_application_stats(self, discord_user_id: str) -> Dict[str, Any]:
        """
        Get student application statistics for congratulatory DMs.
        
        Args:
            discord_user_id: Discord user ID of the student
            
        Returns:
            Dictionary with application statistics including:
            - total_applications: Total count of applications
            - recent_applications: List of recent applications with job details
        """
        # Only support application tracking in database mode
        if self.migration_mode not in ['dual_write', 'database_only']:
            logger.warning("Application tracking requires database mode")
            return {'total_applications': 0, 'recent_applications': []}
            
        return self.database_backend.get_student_application_stats(discord_user_id)

    def get_application_tracking_status(self) -> Dict[str, Any]:
        """
        Get detailed status for application tracking capabilities.
        
        Returns:
            Dictionary with status information including:
            - available: Whether application tracking is available
            - reason: Reason if unavailable
            - migration_mode: Current migration mode
            - database_healthy: Database health status
        """
        status = {
            'available': False,
            'reason': None,
            'migration_mode': self.migration_mode,
            'database_healthy': False
        }
        
        if self.migration_mode not in ['dual_write', 'database_only']:
            status['reason'] = f"Requires database mode, currently: {self.migration_mode}"
            return status
        
        if not self.database_backend:
            status['reason'] = "Database backend not initialized"
            return status
        
        status['database_healthy'] = self.database_backend.health_check()
        if not status['database_healthy']:
            status['reason'] = "Database connection unhealthy"
            return status
        
        status['available'] = True
        return status

    def update_job_posting_with_refresh(self, job: dict) -> bool:
        """Update job posting with differential updates to related data while preserving message tracking.
        
        This method is specifically for the database backend to avoid CASCADE DELETE issues.
        The JSON backend doesn't need this because it doesn't have foreign key constraints.
        
        This method:
        1. Updates the main job_posting record (preserves message tracking)
        2. Differentially updates locations, terms, and degrees (only changes what's different)
        3. Avoids deleting the job_posting itself (which would cascade delete message tracking)
        
        Performance benefits:
        - No-op when no changes to related data
        - Minimal database operations for small changes
        - Preserves existing data that hasn't changed
        
        Args:
            job: Job posting dictionary with all fields
            
        Returns:
            bool: True if successful, False otherwise
        """
        job_id = job['id']
        
        try:
            with self.database_backend.db_manager.session_scope() as session:
                # Import the models we need
                from .database import JobPosting, JobLocation, JobTerm, JobDegree
                
                # 1. Update the main job posting record (preserves message tracking)
                job_posting = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                if not job_posting:
                    logger.error(f"Job posting {job_id} not found for update")
                    return False
                
                # Update all main fields
                job_posting.date_updated = job['date_updated']
                job_posting.url = job['url']
                job_posting.company_name = job['company_name']
                job_posting.title = job['title']
                job_posting.sponsorship = job.get('sponsorship')
                job_posting.active = job.get('active', True)
                job_posting.source = job.get('source')
                job_posting.date_posted = job.get('date_posted')
                job_posting.company_url = job.get('company_url')
                job_posting.is_visible = job.get('is_visible', True)
                job_posting.category = job.get('category')
                
                # Flush the job posting update to ensure it's committed before updating related data
                session.flush()
                
                # 2. Differential updates for related data (only change what's different)
                
                # Handle locations differentially
                if 'locations' in job:
                    existing_locations = {loc.location for loc in session.query(JobLocation).filter(JobLocation.id == job_id)}
                    new_locations = set(job['locations']) if job['locations'] else set()
                    
                    # Remove locations that are no longer needed
                    locations_to_remove = existing_locations - new_locations
                    if locations_to_remove:
                        session.query(JobLocation).filter(
                            JobLocation.id == job_id,
                            JobLocation.location.in_(locations_to_remove)
                        ).delete(synchronize_session=False)
                    
                    # Add new locations (with duplicate protection)
                    locations_to_add = new_locations - existing_locations
                    for location in locations_to_add:
                        try:
                            # Check if this location already exists (race condition protection)
                            existing_location = session.query(JobLocation).filter(
                                JobLocation.id == job_id,
                                JobLocation.location == location
                            ).first()
                            
                            if not existing_location:
                                session.add(JobLocation(id=uuid.UUID(job_id), location=location))
                            else:
                                logger.debug(f"Location '{location}' already exists for job {job_id}, skipping")
                                
                        except Exception as location_error:
                            logger.error(f"Failed to add location '{location}' for job {job_id}: {location_error}")
                            continue
                
                # Handle terms differentially
                if 'terms' in job:
                    existing_terms = {term.term for term in session.query(JobTerm).filter(JobTerm.id == job_id)}
                    new_terms = set(job['terms']) if job['terms'] else set()
                    
                    # Remove terms that are no longer needed
                    terms_to_remove = existing_terms - new_terms
                    if terms_to_remove:
                        session.query(JobTerm).filter(
                            JobTerm.id == job_id,
                            JobTerm.term.in_(terms_to_remove)
                        ).delete(synchronize_session=False)
                    
                    # Add new terms (with duplicate protection)
                    terms_to_add = new_terms - existing_terms
                    for term in terms_to_add:
                        try:
                            # Check if this term already exists (race condition protection)
                            existing_term = session.query(JobTerm).filter(
                                JobTerm.id == job_id,
                                JobTerm.term == term
                            ).first()
                            
                            if not existing_term:
                                session.add(JobTerm(id=uuid.UUID(job_id), term=term))
                            else:
                                logger.debug(f"Term '{term}' already exists for job {job_id}, skipping")
                                
                        except Exception as term_error:
                            logger.error(f"Failed to add term '{term}' for job {job_id}: {term_error}")
                            continue
                
                # Handle degrees differentially
                if 'degrees' in job:
                    existing_degrees = {deg.degree for deg in session.query(JobDegree).filter(JobDegree.id == job_id)}
                    new_degrees = set(job['degrees']) if job['degrees'] else set()
                    
                    # Remove degrees that are no longer needed
                    degrees_to_remove = existing_degrees - new_degrees
                    if degrees_to_remove:
                        session.query(JobDegree).filter(
                            JobDegree.id == job_id,
                            JobDegree.degree.in_(degrees_to_remove)
                        ).delete(synchronize_session=False)
                    
                    # Add new degrees (with duplicate protection)
                    degrees_to_add = new_degrees - existing_degrees
                    for degree in degrees_to_add:
                        try:
                            # Double-check the job posting still exists before each insert
                            job_still_exists = session.query(JobPosting).filter(JobPosting.id == job_id).first()
                            if not job_still_exists:
                                logger.error(f"Job posting {job_id} disappeared during degree update")
                                return False
                            
                            # Check if this degree already exists (race condition protection)
                            existing_degree = session.query(JobDegree).filter(
                                JobDegree.id == job_id,
                                JobDegree.degree == degree
                            ).first()
                            
                            if not existing_degree:
                                session.add(JobDegree(id=uuid.UUID(job_id), degree=degree))
                            else:
                                logger.debug(f"Degree '{degree}' already exists for job {job_id}, skipping")
                                
                        except Exception as degree_error:
                            logger.error(f"Failed to add degree '{degree}' for job {job_id}: {degree_error}")
                            # Continue with other degrees instead of failing the whole operation
                            continue
                
                # Commit all changes
                session.commit()
                logger.debug(f"Successfully updated job posting {job_id} with refresh")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job posting {job_id} with refresh: {e}")
            return False