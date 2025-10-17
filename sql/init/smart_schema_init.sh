#!/bin/bash
# Smart PostgreSQL Initialization Script
# This script chooses the appropriate initialization approach:
# - For new databases: Use latest complete schema from sql/schema/
# - For existing: Skip (PostgreSQL auto-init only runs on empty databases)

set -e

# PostgreSQL auto-init variables
export PGDATABASE="$POSTGRES_DB"
export PGUSER="$POSTGRES_USER"

echo "🔍 Checking database initialization requirements..."

# Check if database is empty (this is PostgreSQL's auto-init, so it should be)
TABLE_COUNT=$(psql -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo "ℹ️  Database already contains tables ($TABLE_COUNT found). Skipping initialization."
    exit 0
fi

echo "🏗️  Initializing new database with latest schema..."

# Find the highest version schema file from the schema directory
LATEST_SCHEMA=""
HIGHEST_VERSION=0

for schema_file in /schema/V*__*.sql; do
    if [ -f "$schema_file" ]; then
        # Extract version number (V1, V2, etc.)
        filename=$(basename "$schema_file")
        version=$(echo "$filename" | sed 's/V\([0-9]\+\)__.*/\1/')
        
        if [ "$version" -gt "$HIGHEST_VERSION" ]; then
            HIGHEST_VERSION="$version"
            LATEST_SCHEMA="$schema_file"
        fi
    fi
done

if [ -n "$LATEST_SCHEMA" ]; then
    echo "📋 Applying latest schema V${HIGHEST_VERSION}: $(basename "$LATEST_SCHEMA")..."
    psql -f "$LATEST_SCHEMA"
else
    echo "⚠️  No versioned schema files found, falling back to legacy init..."
    # Fallback to old init files if new structure not available
    for init_file in /docker-entrypoint-initdb.d/0*.sql; do
        if [ -f "$init_file" ]; then
            echo "📋 Applying: $(basename "$init_file")..."
            psql -f "$init_file"
        fi
    done
fi

# Add version tracking
if [ -f "/docker-entrypoint-initdb.d/version_tracking.sql" ]; then
    echo "📊 Adding version tracking..."
    psql -f "/docker-entrypoint-initdb.d/version_tracking.sql"
fi

echo "✅ Database initialization completed successfully!"