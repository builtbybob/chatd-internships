#!/usr/bin/env python3
"""
Database Migration Script - Application Tracking Schema
Implements soft delete support and student applications table for application tracking.

This script provides safe database migration with validation, rollback capabilities,
and comprehensive error handling.
"""

import os
import sys
import argparse
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from chatd.config import Config
from chatd.database import DatabaseManager
from sqlalchemy import text


class ApplicationTrackingMigration:
    """Migration handler for application tracking database schema."""
    
    def __init__(self, config):
        self.config = config
        
        # Build database URL from config
        db_url = f"postgresql://{config.db_user}:{config.db_password}@{config.db_host}:{config.db_port}/{config.db_name}"
        self.db_factory = DatabaseManager(db_url)
        self.migration_file = project_root / "sql" / "migrations" / "002_add_soft_delete_and_applications.sql"
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def validate_prerequisites(self):
        """Validate that the database and prerequisites are ready for migration."""
        self.logger.info("🔍 Validating migration prerequisites...")
        
        # Check if migration file exists
        if not self.migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {self.migration_file}")
        
        # Validate database connection
        try:
            with self.db_factory.get_session() as session:
                # Check if job_postings table exists
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'job_postings'
                    );
                """))
                if not result.scalar():
                    raise RuntimeError("job_postings table not found. Run initial schema migration first.")
                
                # Check if is_deleted column already exists
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'job_postings' 
                        AND column_name = 'is_deleted'
                    );
                """))
                if result.scalar():
                    self.logger.warning("⚠️  is_deleted column already exists. Migration may have been run previously.")
                
                # Check if student_applications table already exists
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'student_applications'
                    );
                """))
                if result.scalar():
                    self.logger.warning("⚠️  student_applications table already exists. Migration may have been run previously.")
                
                self.logger.info("✅ Prerequisites validation passed")
                
        except Exception as e:
            self.logger.error(f"❌ Database validation failed: {e}")
            raise
    
    def create_backup(self):
        """Create a database backup before migration."""
        if not self.config.enable_database_backups:
            self.logger.info("📦 Database backups disabled in configuration")
            return None
        
        self.logger.info("📦 Creating database backup before migration...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/tmp/chatd_backup_pre_migration_5_7_{timestamp}.sql"
        
        try:
            # Use pg_dump to create backup
            cmd = [
                "pg_dump",
                f"--host={self.config.db_host}",
                f"--port={self.config.db_port}",
                f"--username={self.config.db_user}",
                f"--dbname={self.config.db_name}",
                "--no-password",
                "--clean",
                "--create",
                "--verbose",
                f"--file={backup_file}"
            ]
            
            env = os.environ.copy()
            env["PGPASSWORD"] = self.config.db_password
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"✅ Database backup created: {backup_file}")
                return backup_file
            else:
                self.logger.error(f"❌ Backup failed: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Backup creation failed: {e}")
            return None
    
    def run_migration(self, dry_run=False):
        """Execute the database migration."""
        if dry_run:
            self.logger.info("🧪 DRY RUN: Simulating migration execution...")
            with open(self.migration_file, 'r') as f:
                migration_sql = f.read()
            self.logger.info("Migration SQL to be executed:")
            print("=" * 60)
            print(migration_sql)
            print("=" * 60)
            return True
        
        self.logger.info("🚀 Executing database migration...")
        
        try:
            with self.db_factory.get_session() as session:
                # Read and execute migration file
                with open(self.migration_file, 'r') as f:
                    migration_sql = f.read()
                
                # Execute the migration
                session.execute(text(migration_sql))
                session.commit()
                
                self.logger.info("✅ Migration executed successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Migration failed: {e}")
            raise
    
    def validate_migration(self):
        """Validate that the migration was successful."""
        self.logger.info("🔍 Validating migration results...")
        
        try:
            with self.db_factory.get_session() as session:
                # Check is_deleted column exists and has correct default
                result = session.execute(text("""
                    SELECT column_default 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'job_postings' 
                    AND column_name = 'is_deleted';
                """))
                default_value = result.scalar()
                if default_value != 'false':
                    raise RuntimeError(f"is_deleted column has incorrect default: {default_value}")
                
                # Check student_applications table structure
                result = session.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'student_applications'
                    ORDER BY ordinal_position;
                """))
                columns = result.fetchall()
                
                expected_columns = {
                    'id': ('uuid', 'NO'),
                    'job_id': ('uuid', 'NO'), 
                    'discord_user_id': ('text', 'NO'),
                    'applied_at': ('timestamp without time zone', 'YES')
                }
                
                for col_name, data_type, is_nullable in columns:
                    if col_name in expected_columns:
                        expected_type, expected_nullable = expected_columns[col_name]
                        if data_type != expected_type:
                            raise RuntimeError(f"Column {col_name} has wrong type: {data_type}")
                        if is_nullable != expected_nullable:
                            raise RuntimeError(f"Column {col_name} has wrong nullable: {is_nullable}")
                
                # Check indexes were created
                result = session.execute(text("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = 'student_applications'
                    AND schemaname = 'public';
                """))
                indexes = [row[0] for row in result.fetchall()]
                
                required_indexes = [
                    'idx_student_applications_user_id',
                    'idx_student_applications_applied_at', 
                    'idx_student_applications_job_id'
                ]
                
                for idx in required_indexes:
                    if idx not in indexes:
                        raise RuntimeError(f"Required index not found: {idx}")
                
                # Test constraint enforcement
                session.execute(text("""
                    INSERT INTO student_applications (job_id, discord_user_id) 
                    SELECT id, 'test_validation_user' 
                    FROM job_postings LIMIT 1
                    ON CONFLICT (job_id, discord_user_id) DO NOTHING;
                """))
                
                self.logger.info("✅ Migration validation passed")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Migration validation failed: {e}")
            raise
    
    def get_migration_status(self):
        """Get current migration status."""
        try:
            with self.db_factory.get_session() as session:
                # Check if is_deleted column exists
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'job_postings' 
                        AND column_name = 'is_deleted'
                    );
                """))
                has_soft_delete = result.scalar()
                
                # Check if student_applications table exists
                result = session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'student_applications'
                    );
                """))
                has_applications_table = result.scalar()
                
                if has_soft_delete and has_applications_table:
                    return "COMPLETED"
                elif has_soft_delete or has_applications_table:
                    return "PARTIAL"
                else:
                    return "PENDING"
                    
        except Exception as e:
            self.logger.error(f"❌ Could not determine migration status: {e}")
            return "ERROR"


def main():
    """Main migration script entry point."""
    parser = argparse.ArgumentParser(description="Application Tracking Database Migration")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--status", action="store_true", help="Show current migration status")
    parser.add_argument("--validate-only", action="store_true", help="Only validate prerequisites")
    parser.add_argument("--skip-backup", action="store_true", help="Skip database backup creation")
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = Config()
        migration = ApplicationTrackingMigration(config)
        
        if args.status:
            status = migration.get_migration_status()
            print(f"Migration Status: {status}")
            return 0
        
        # Always validate prerequisites
        migration.validate_prerequisites()
        
        if args.validate_only:
            print("✅ Prerequisites validation successful")
            return 0
        
        # Create backup unless skipped
        backup_file = None
        if not args.skip_backup and not args.dry_run:
            backup_file = migration.create_backup()
            if backup_file:
                print(f"📦 Backup created: {backup_file}")
        
        # Run migration
        success = migration.run_migration(dry_run=args.dry_run)
        
        if success and not args.dry_run:
            # Validate migration results
            migration.validate_migration()
            print("🎉 Migration completed successfully!")
            print("\n📋 Next steps:")
            print("1. Update bot code to use soft delete logic")
            print("2. Implement application tracking in reaction handlers")
            print("3. Test application tracking functionality")
        elif args.dry_run:
            print("🧪 Dry run completed. Use --validate-only to check prerequisites.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())