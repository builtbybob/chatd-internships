# Database Schema Management - New Structure

## Overview

This document describes the new database schema management structure implemented for the ChatD Internships project. The system follows industry best practices and provides a clear separation between complete schema states and incremental migrations.

## Directory Structure

```
sql/
├── schema/                                    # Complete database states
│   ├── V1__initial_schema.sql                # Original basic schema
│   └── V2__with_soft_delete_and_apps.sql     # Current schema with all features
├── migrations/                               # Incremental upgrades
│   └── V2__add_soft_delete_and_apps.sql     # Upgrade V1 → V2
└── init/                                     # Infrastructure
    ├── 000_smart_init.sh                    # Smart initialization script
    └── version_tracking.sql                 # Migration tracking table
```

## Key Principles

### 1. Schema Files (Complete States)
- **Purpose**: Define complete database state at specific versions
- **Usage**: New installations always use the latest schema file
- **Immutable**: Once created, schema files should never be modified
- **Naming**: `V{number}__{description}.sql` (follows Flyway conventions)

### 2. Migration Files (Incremental Changes)
- **Purpose**: Upgrade existing databases from one version to another
- **Usage**: Applied sequentially to existing installations
- **Naming**: `V{number}__{description}.sql` (matches target schema version)

### 3. Version Tracking
- **Purpose**: Track which migrations have been applied to each database
- **Implementation**: `schema_migrations` table with version, timestamp, and description
- **Benefits**: Prevents duplicate migrations, provides audit trail

## Operational Workflows

### New Environment Setup
```bash
# Docker automatically runs 000_smart_init.sh which:
# 1. Detects it's a new database
# 2. Applies latest schema (V2__with_soft_delete_and_apps.sql)
# 3. Sets up version tracking
# 4. Marks database as current version
```

### Existing Environment Upgrade
```bash
# Use schema manager to apply pending migrations:
python scripts/schema_manager.py --status    # Check current version
python scripts/schema_manager.py --upgrade   # Apply pending migrations
```

### Adding New Features (Future)
When adding new features (e.g., user preferences):

1. **Create Migration File**:
   ```sql
   -- sql/migrations/V3__add_user_preferences.sql
   CREATE TABLE user_preferences (...);
   ALTER TABLE job_postings ADD COLUMN ...;
   ```

2. **Create New Complete Schema**:
   ```sql
   -- sql/schema/V3__with_user_preferences.sql
   -- Copy V2 schema and add new features directly
   ```

3. **Update Setup Scripts**: Change references to use V3 as latest

## Tools

### Schema Manager (`scripts/schema_manager.py`)
- `--status`: Show current database version
- `--init`: Initialize new database with latest schema
- `--upgrade`: Upgrade legacy database to latest version
- `--migrate <file>`: Apply specific migration
- `--validate`: Check schema integrity

### Smart Init Script (`sql/init/000_smart_init.sh`)
- Automatically detects database state
- Applies appropriate initialization strategy
- Used by Docker during container startup

## Benefits of This Approach

1. **Clear Separation**: Schema states vs incremental changes
2. **Industry Standard**: Follows Flyway/Liquibase conventions
3. **Future-Proof**: Easy migration to formal tools like Flyway
4. **Safe Operations**: Version tracking prevents conflicts
5. **Testing**: Can test both fresh installs and migration paths
6. **Rollback Ready**: Each schema file represents a known good state

## Migration from Previous System

The old files are preserved for reference:
- `sql/init/001_initial_schema.sql` → Reference only
- `sql/init/002_complete_schema.sql` → Reference only
- `sql/migrations/002_add_soft_delete_and_applications.sql` → Reference only

New installations will automatically use the latest versioned schema structure.

## Future Evolution

This structure prepares the project for potential future adoption of professional migration tools:
- **File naming** already matches Flyway conventions
- **Version tracking** is compatible with migration tools
- **Directory structure** follows industry patterns
- **Migration concepts** are already established

The system can scale from "focused Discord bot" to "enterprise application" without major restructuring.