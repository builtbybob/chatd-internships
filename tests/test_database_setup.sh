#!/bin/bash
# test-database-setup.sh
# Test script to verify PostgreSQL database setup

set -e

echo "🔍 Testing PostgreSQL Database Setup..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "📦 Starting PostgreSQL container..."
cd /home/apathy/chatd-internships

# Start the database container
docker-compose -f docker-compose.database.yml up -d

echo "⏳ Waiting for PostgreSQL to be ready..."
# Wait for health check to pass
timeout 60s bash -c 'until docker-compose -f docker-compose.database.yml exec chatd-postgres pg_isready -U chatd -d chatd; do sleep 2; done'

if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL is ready!"
else
    echo "❌ PostgreSQL failed to start within 60 seconds"
    docker-compose -f docker-compose.database.yml logs chatd-postgres
    exit 1
fi

echo "🔍 Testing database connection and schema..."

# Test basic connection
docker-compose -f docker-compose.database.yml exec -T chatd-postgres psql -U chatd -d chatd -c "SELECT version();"

if [ $? -eq 0 ]; then
    echo "✅ Database connection successful!"
else
    echo "❌ Failed to connect to database"
    exit 1
fi

# Test schema by querying tables
echo "📊 Checking database schema..."
docker-compose -f docker-compose.database.yml exec -T chatd-postgres psql -U chatd -d chatd -c "\dt"

# Test the readable view
echo "📋 Testing job_postings_readable view..."
docker-compose -f docker-compose.database.yml exec -T chatd-postgres psql -U chatd -d chatd -c "
SELECT company_name, title, posted_timestamp, locations, terms 
FROM job_postings_readable 
LIMIT 5;
"

echo "🎉 Database setup test completed successfully!"
echo ""
echo "📝 Next steps:"
echo "   1. Database is running at localhost:5432"
echo "   2. Connection details:"
echo "      - Database: chatd"
echo "      - User: chatd" 
echo "      - Password: \${POSTGRES_PASSWORD} (default: chatd_dev_password)"
echo "   3. To stop: docker-compose -f docker-compose.database.yml down"
echo "   4. To view logs: docker-compose -f docker-compose.database.yml logs -f"
echo ""
echo "🔧 Ready to proceed to Phase 2: Database Models & ORM"