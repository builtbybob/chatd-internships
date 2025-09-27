"""
Database models and connection management for ChatD Internships Bot.

This module provides SQLAlchemy ORM models that map to the PostgreSQL database
schema, along with database connection factory and session management.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, String, BigInteger, Boolean, Text, ForeignKey, text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

logger = logging.getLogger(__name__)

Base = declarative_base()


class JobPosting(Base):
    """Main job postings table with core job information."""
    
    __tablename__ = 'job_postings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date_updated = Column(BigInteger, nullable=False, index=True)
    url = Column(Text, nullable=False, unique=True)
    company_name = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    sponsorship = Column(Text, nullable=True)
    active = Column(Boolean, default=True, index=True)
    source = Column(Text, nullable=True)
    date_posted = Column(BigInteger, nullable=True, index=True)
    company_url = Column(Text, nullable=True)
    is_visible = Column(Boolean, default=True, index=True)
    
    # Relationships
    locations = relationship("JobLocation", back_populates="job_posting", cascade="all, delete-orphan")
    terms = relationship("JobTerm", back_populates="job_posting", cascade="all, delete-orphan")
    message_tracking = relationship("MessageTracking", back_populates="job_posting", 
                                  uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<JobPosting(id='{self.id}', company='{self.company_name}', title='{self.title}')>"
    
    @property
    def location_list(self) -> List[str]:
        """Get list of location strings."""
        return [loc.location for loc in self.locations]
    
    @property
    def term_list(self) -> List[str]:
        """Get list of term strings."""
        return [term.term for term in self.terms]


class JobLocation(Base):
    """Normalized locations table (one-to-many with job postings)."""
    
    __tablename__ = 'job_locations'
    
    id = Column(UUID(as_uuid=True), ForeignKey('job_postings.id', ondelete='CASCADE'), primary_key=True)
    location = Column(Text, nullable=False, primary_key=True)
    
    # Relationship
    job_posting = relationship("JobPosting", back_populates="locations")
    
    def __repr__(self):
        return f"<JobLocation(id='{self.id}', location='{self.location}')>"


class JobTerm(Base):
    """Normalized terms table (one-to-many with job postings)."""
    
    __tablename__ = 'job_terms'
    
    id = Column(UUID(as_uuid=True), ForeignKey('job_postings.id', ondelete='CASCADE'), primary_key=True)
    term = Column(Text, nullable=False, primary_key=True)
    
    # Relationship
    job_posting = relationship("JobPosting", back_populates="terms")
    
    def __repr__(self):
        return f"<JobTerm(id='{self.id}', term='{self.term}')>"


class MessageTracking(Base):
    """Message tracking table (one-to-one with job postings)."""
    
    __tablename__ = 'message_tracking'
    
    id = Column(UUID(as_uuid=True), ForeignKey('job_postings.id', ondelete='CASCADE'), primary_key=True)
    message_id = Column(Text, nullable=False, index=True)
    channel_id = Column(Text, nullable=False, index=True)
    posted_at = Column(DateTime, nullable=False, default=func.current_timestamp(), index=True)
    
    # Relationship
    job_posting = relationship("JobPosting", back_populates="message_tracking")
    
    def __repr__(self):
        return f"<MessageTracking(id='{self.id}', message_id='{self.message_id}', channel_id='{self.channel_id}')>"


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection URL
            echo: Whether to log SQL queries (for debugging)
        """
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=echo)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created/verified")
        
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
        
    @contextmanager
    def session_scope(self):
        """
        Context manager for database sessions with automatic cleanup.
        
        Usage:
            with db_manager.session_scope() as session:
                # database operations
                pass
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            
    def test_connection(self) -> bool:
        """
        Test database connectivity.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


def get_database_url(config) -> str:
    """
    Build PostgreSQL connection URL from configuration.
    
    Args:
        config: Configuration object with database settings
        
    Returns:
        PostgreSQL connection URL
    """
    return (f"postgresql://{config.DB_USER}:{config.DB_PASSWORD}"
            f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")


def create_database_manager(config, echo: bool = False) -> DatabaseManager:
    """
    Create a database manager instance from configuration.
    
    Args:
        config: Configuration object with database settings
        echo: Whether to log SQL queries (for debugging)
        
    Returns:
        DatabaseManager instance
    """
    database_url = get_database_url(config)
    return DatabaseManager(database_url, echo=echo)


# Database operations helper functions

def job_posting_from_dict(job_data: Dict[str, Any]) -> JobPosting:
    """
    Create a JobPosting instance from dictionary data (typically from JSON).
    
    Args:
        job_data: Dictionary containing job posting data
        
    Returns:
        JobPosting instance with related objects
    """
    # Create main job posting
    job_posting = JobPosting(
        id=uuid.UUID(job_data['id']),
        date_updated=job_data['date_updated'],
        url=job_data['url'],
        company_name=job_data['company_name'],
        title=job_data['title'],
        sponsorship=job_data.get('sponsorship'),
        active=job_data.get('active', True),
        source=job_data.get('source'),
        date_posted=job_data.get('date_posted'),
        company_url=job_data.get('company_url'),
        is_visible=job_data.get('is_visible', True)
    )
    
    # Add locations
    for location in job_data.get('locations', []):
        job_location = JobLocation(
            id=job_posting.id,
            location=location
        )
        job_posting.locations.append(job_location)
    
    # Add terms
    for term in job_data.get('terms', []):
        job_term = JobTerm(
            id=job_posting.id,
            term=term
        )
        job_posting.terms.append(job_term)
    
    return job_posting


def job_posting_to_dict(job_posting: JobPosting) -> Dict[str, Any]:
    """
    Convert JobPosting instance to dictionary (for JSON serialization).
    
    Args:
        job_posting: JobPosting instance
        
    Returns:
        Dictionary representation
    """
    return {
        'id': str(job_posting.id),
        'date_updated': job_posting.date_updated,
        'url': job_posting.url,
        'company_name': job_posting.company_name,
        'title': job_posting.title,
        'sponsorship': job_posting.sponsorship,
        'active': job_posting.active,
        'source': job_posting.source,
        'date_posted': job_posting.date_posted,
        'company_url': job_posting.company_url,
        'is_visible': job_posting.is_visible,
        'locations': job_posting.location_list,
        'terms': job_posting.term_list
    }