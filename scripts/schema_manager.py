#!/usr/bin/env python3
"""
Database Schema Management Tool
Handles database initialization, migration tracking, and schema updates.

This tool provides:
- Smart schema initialization (latest schema for new databases)
- Migration tracking with version control
- Rollback capabilities for development
- Schema validation and health checks
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from chatd.config import Config
from chatd.database import DatabaseManager
from sqlalchemy import text


class SchemaManager:
    """Comprehensive database schema management."""
    
    def __init__(self, config):
        self.config = config
        
        # Build database URL from config
        db_url = f"postgresql://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}"
        self.db_factory = DatabaseManager(db_url)
        
        # Schema paths
        self.schema_dir = project_root / "sql" / "schema"
        self.init_dir = project_root / "sql" / "init"
        self.migrations_dir = project_root / "sql" / "migrations"
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_database_status(self):
        """Check database status and schema version."""
        try:
            with self.db_factory.get_session() as session:
                # Check if any tables exist
                result = session.execute(text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE';
                """))
                table_count = result.scalar()
                
                if table_count == 0:
                    return "EMPTY"
                
                # Check if schema_migrations table exists
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'schema_migrations'
                    );
                """))
                
                if not result.scalar():
                    return "LEGACY"  # Has tables but no version tracking
                
                # Get latest migration version
                result = session.execute(text("""
                    SELECT version, applied_at 
                    FROM schema_migrations 
                    ORDER BY applied_at DESC 
                    LIMIT 1;
                """))
                latest = result.fetchone()
                
                if latest:
                    return f"VERSIONED:{latest[0]}"
                else:
                    return "LEGACY"
                    
        except Exception as e:
            self.logger.error(f"Could not determine database status: {e}")
            return "ERROR"
    
    def initialize_new_database(self):
        """Initialize a new database with the latest complete schema."""
        self.logger.info("🏗️  Initializing new database with latest schema...")
        
        status = self.get_database_status()
        if status != "EMPTY":
            raise RuntimeError(f"Database is not empty (status: {status}). Use migration commands for existing databases.")
        
        try:
            with self.db_factory.get_session() as session:
                # Find the latest schema file (highest V number)
                latest_schema = None
                if self.schema_dir.exists():
                    schema_files = sorted(self.schema_dir.glob("V*__*.sql"))
                    if schema_files:
                        latest_schema = schema_files[-1]  # Get the latest version
                
                if not latest_schema:
                    raise FileNotFoundError(f"No schema files found in {self.schema_dir}")
                
                self.logger.info(f"📋 Applying latest schema: {latest_schema.name}")
                with open(latest_schema, 'r') as f:
                    schema_sql = f.read()
                
                session.execute(text(schema_sql))
                
                # Add version tracking
                version_tracking = self.init_dir / "version_tracking.sql"
                if version_tracking.exists():
                    with open(version_tracking, 'r') as f:
                        version_sql = f.read()
                    session.execute(text(version_sql))
                
                session.commit()
                self.logger.info(f"✅ Database initialized successfully with {latest_schema.name}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Database initialization failed: {e}")
            raise
    
    def apply_migration(self, migration_file):
        """Apply a specific migration file."""
        self.logger.info(f"🔄 Applying migration: {migration_file}")
        
        migration_path = self.migrations_dir / migration_file
        if not migration_path.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_path}")
        
        try:
            with self.db_factory.get_session() as session:
                # Check if already applied
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM schema_migrations 
                        WHERE version = :version
                    );
                """), {"version": migration_file.replace('.sql', '')})
                
                if result.scalar():
                    self.logger.info(f"⏩ Migration {migration_file} already applied, skipping")
                    return True
                
                # Apply migration
                with open(migration_path, 'r') as f:
                    migration_sql = f.read()
                
                session.execute(text(migration_sql))
                
                # Record migration
                session.execute(text("""
                    INSERT INTO schema_migrations (version, applied_at, description) 
                    VALUES (:version, :applied_at, :description)
                """), {
                    "version": migration_file.replace('.sql', ''),
                    "applied_at": datetime.now(),
                    "description": f"Applied migration {migration_file}"
                })
                
                session.commit()
                self.logger.info(f"✅ Migration {migration_file} applied successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Migration {migration_file} failed: {e}")
            raise
    
    def upgrade_legacy_database(self):
        """Upgrade a legacy database (has tables but no version tracking)."""
        self.logger.info("🔄 Upgrading legacy database to versioned schema...")
        
        try:
            with self.db_factory.get_session() as session:
                # Add version tracking table
                version_tracking = self.init_dir / "version_tracking.sql"
                if version_tracking.exists():
                    with open(version_tracking, 'r') as f:
                        version_sql = f.read()
                    session.execute(text(version_sql))
                
                # Check what migrations need to be applied
                # Check if soft delete features exist
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'job_postings' 
                        AND column_name = 'is_deleted'
                    );
                """))
                
                has_soft_delete = result.scalar()
                
                if not has_soft_delete:
                    # Apply migration V2
                    migration_v2 = self.migrations_dir / "V2__add_soft_delete_and_apps.sql"
                    if migration_v2.exists():
                        with open(migration_v2, 'r') as f:
                            migration_sql = f.read()
                        session.execute(text(migration_sql))
                        
                        # Record this migration
                        session.execute(text("""
                            INSERT INTO schema_migrations (version, applied_at, description) 
                            VALUES ('V2__add_soft_delete_and_apps', :applied_at, 'Legacy upgrade: soft delete and applications')
                        """), {"applied_at": datetime.now()})
                
                session.commit()
                self.logger.info("✅ Legacy database upgraded successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Legacy database upgrade failed: {e}")
            raise
    
    def validate_schema(self):
        """Validate current database schema integrity."""
        self.logger.info("🔍 Validating database schema...")
        
        try:
            with self.db_factory.get_session() as session:
                # Check required tables exist
                required_tables = [
                    'job_postings', 'job_locations', 'job_terms', 'job_degrees',
                    'message_tracking', 'student_applications', 'schema_migrations'
                ]
                
                for table in required_tables:
                    result = session.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = :table_name
                        );
                    """), {"table_name": table})
                    
                    if not result.scalar():
                        raise RuntimeError(f"Required table missing: {table}")
                
                # Check job_postings has soft delete column
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'job_postings' 
                        AND column_name = 'is_deleted'
                    );
                """))
                
                if not result.scalar():
                    raise RuntimeError("job_postings table missing is_deleted column")
                
                # Check views exist
                required_views = ['job_postings_readable', 'active_job_postings', 'application_statistics']
                for view in required_views:
                    result = session.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.views 
                            WHERE table_schema = 'public' 
                            AND table_name = :view_name
                        );
                    """), {"view_name": view})
                    
                    if not result.scalar():
                        raise RuntimeError(f"Required view missing: {view}")
                
                self.logger.info("✅ Schema validation passed")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Schema validation failed: {e}")
            raise
    
    def list_migrations(self):
        """List all available and applied migrations."""
        print("📋 Migration Status:")
        print("-" * 50)
        
        try:
            with self.db_factory.get_session() as session:
                # Get applied migrations
                applied = set()
                try:
                    result = session.execute(text("""
                        SELECT version, applied_at 
                        FROM schema_migrations 
                        ORDER BY applied_at
                    """))
                    for version, applied_at in result.fetchall():
                        applied.add(version)
                        print(f"✅ {version} (applied: {applied_at})")
                except:
                    print("ℹ️  No version tracking table found")
                
                # Check available migrations
                if self.migrations_dir.exists():
                    for migration_file in sorted(self.migrations_dir.glob("*.sql")):
                        migration_name = migration_file.stem
                        if migration_name not in applied:
                            print(f"⏳ {migration_name} (pending)")
                
        except Exception as e:
            print(f"❌ Could not list migrations: {e}")


def main():
    """Main schema management entry point."""
    parser = argparse.ArgumentParser(description="Database Schema Management Tool")
    parser.add_argument("--status", action="store_true", help="Show database status")
    parser.add_argument("--init", action="store_true", help="Initialize new database with latest schema")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade legacy database to latest version")
    parser.add_argument("--migrate", type=str, help="Apply specific migration file")
    parser.add_argument("--validate", action="store_true", help="Validate schema integrity")
    parser.add_argument("--list", action="store_true", help="List all migrations and their status")
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = Config()
        manager = SchemaManager(config)
        
        if args.status:
            status = manager.get_database_status()
            print(f"Database Status: {status}")
            return 0
        
        if args.list:
            manager.list_migrations()
            return 0
        
        if args.init:
            manager.initialize_new_database()
            return 0
        
        if args.upgrade:
            manager.upgrade_legacy_database()
            return 0
        
        if args.migrate:
            manager.apply_migration(args.migrate)
            return 0
        
        if args.validate:
            manager.validate_schema()
            return 0
        
        # If no specific action, show status and recommendations
        status = manager.get_database_status()
        print(f"Database Status: {status}")
        
        if status == "EMPTY":
            print("💡 Recommendation: Use --init to initialize with latest schema")
        elif status == "LEGACY":
            print("💡 Recommendation: Use --upgrade to add version tracking and latest features")
        elif status.startswith("VERSIONED:"):
            print("✅ Database is up to date with version tracking")
        
        return 0
        
    except Exception as e:
        print(f"❌ Schema management failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())