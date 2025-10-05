#!/bin/bash
# setup-development-environment.sh
# Automated setup script for ThatdInternships development environment

set -e

echo "🚀 Setting up ThatdInternships development environment..."
echo "=================================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Configuration
DEV_DIR="/opt/thatd-internships"
PROD_DIR="/opt/chatd"

# Step 1: Create directory structure
echo "📁 Creating development directory structure..."
mkdir -p "$DEV_DIR"/{data,logs}
mkdir -p "$DEV_DIR"/sql/init

# Step 2: Copy repository
echo "📥 Cloning repository for development..."
if [ ! -d "$DEV_DIR/Summer2026-Internships" ]; then
    cd "$DEV_DIR"
    git clone https://github.com/SimplifyJobs/Summer2026-Internships.git
    echo "✅ Repository cloned"
else
    echo "✅ Repository already exists"
fi

# Step 3: Copy SQL initialization files
echo "🗄️  Copying database schema files..."
cp -r "$PROD_DIR"/sql/* "$DEV_DIR"/sql/
echo "✅ SQL files copied"

# Step 4: Copy and modify source code
echo "📄 Copying source code..."
cp -r "$PROD_DIR"/{chatd,tests,requirements.txt,Dockerfile,main.py} "$DEV_DIR"/
echo "✅ Source code copied"

# Step 5: Create development docker-compose.yml
echo "🐳 Creating development docker-compose.yml..."
cat > "$DEV_DIR/docker-compose.yml" << 'EOF'
version: '3.8'
services:
  thatd-postgres:
    image: postgres:15-alpine
    container_name: thatd-postgres
    environment:
      POSTGRES_DB: thatd
      POSTGRES_USER: thatd
      POSTGRES_PASSWORD: ${DB_PASSWORD:-thatd_dev_password}
    volumes:
      - thatd_postgres_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "5433:5432"  # External port 5433 to avoid conflicts with production
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U thatd -d thatd"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - thatd-network

  thatd-bot:
    build: .
    container_name: thatd-bot
    environment:
      # Load environment variables from the host or .env file
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - CHANNEL_IDS=${CHANNEL_IDS}
      - DB_PASSWORD=${DB_PASSWORD}
      - MIGRATION_MODE=${MIGRATION_MODE:-database_only}
      - LOG_LEVEL=${LOG_LEVEL:-DEBUG}
      - ENABLE_REACTIONS=${ENABLE_REACTIONS:-true}
      - MAX_POST_AGE_DAYS=${MAX_POST_AGE_DAYS:-2}
      - CHECK_INTERVAL_MINUTES=${CHECK_INTERVAL_MINUTES:-1}
      - MAX_RETRIES=${MAX_RETRIES:-2}
      # Section 4.1 optimizations
      - MESSAGE_POST_DELAY_MS=${MESSAGE_POST_DELAY_MS:-100}
      - REACTION_DELAY_MS=${REACTION_DELAY_MS:-500}
      - BATCH_PROCESSING_DELAY_MS=${BATCH_PROCESSING_DELAY_MS:-50}
      # Database configuration
      - DB_HOST=thatd-postgres
      - DB_PORT=5432
      - DB_NAME=thatd
      - DB_USER=thatd
      - DB_TYPE=postgresql
      # Timezone configuration
      - TZ=${TZ:-UTC}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./Summer2026-Internships:/app/Summer2026-Internships
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
    depends_on:
      thatd-postgres:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - thatd-network
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f python3 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

volumes:
  thatd_postgres_data:
    driver: local

networks:
  thatd-network:
    driver: bridge
EOF
echo "✅ docker-compose.yml created"

# Step 6: Create development .env template
echo "⚙️  Creating development .env template..."
cat > "$DEV_DIR/.env.template" << 'EOF'
###############################################################
# ThatdInternships Development Environment Configuration
###############################################################

# Discord Bot Configuration (ThatdInternships bot)
DISCORD_TOKEN=your_thatd_bot_token_here
CHANNEL_IDS=your_test_channel_ids_here

# Database Configuration (automatically uses thatd-postgres)
DB_PASSWORD=thatd_dev_password

# Development Settings  
MIGRATION_MODE=database_only
LOG_LEVEL=DEBUG
ENABLE_REACTIONS=true
CHECK_INTERVAL_MINUTES=1
MAX_POST_AGE_DAYS=2
MAX_RETRIES=2

# Section 4.1 Performance Optimizations
MESSAGE_POST_DELAY_MS=100
REACTION_DELAY_MS=500
BATCH_PROCESSING_DELAY_MS=50

# Database Configuration (advanced)
DB_CONNECTION_POOL_SIZE=3
DB_AUTO_VACUUM=true
DB_HEALTH_CHECK_INTERVAL=60
DB_MIGRATION_BATCH_SIZE=50
DB_BACKUP_RETENTION_DAYS=7
EOF

# Step 7: Copy existing .env.test if it exists, otherwise use template
if [ -f "$PROD_DIR/.env.test" ]; then
    echo "📋 Copying existing .env.test configuration..."
    cp "$PROD_DIR/.env.test" "$DEV_DIR/.env"
else
    echo "📋 Using .env template..."
    cp "$DEV_DIR/.env.template" "$DEV_DIR/.env"
fi
echo "✅ .env configuration ready"

# Step 8: Set proper ownership
echo "🔒 Setting proper ownership..."
chown -R root:root "$DEV_DIR"
chmod +x "$DEV_DIR"/scripts/*.sh 2>/dev/null || true
echo "✅ Ownership configured"

# Step 9: Create thatd management commands
echo "🛠️  Setting up thatd management commands..."
if [ -f "$DEV_DIR/scripts/create-management-scripts.sh" ]; then
    cd "$DEV_DIR"
    CHATD_PREFIX="thatd" ./scripts/create-management-scripts.sh
    echo "✅ thatd commands created"
else
    echo "⚠️  Management scripts not found, skipping command creation"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo "=================================================="
echo ""
echo "📋 Next steps:"
echo "1. Edit $DEV_DIR/.env with your ThatdInternships Discord bot token"
echo "2. Configure test channel IDs in the .env file"
echo "3. Build and deploy the development environment:"
echo "   cd $DEV_DIR"
echo "   sudo thatd build"
echo "   sudo thatd deploy"
echo "   sudo thatd status"
echo ""
echo "🔧 Development commands:"
echo "   sudo thatd status    # Check development environment status"
echo "   sudo thatd logs -f   # Follow development logs"
echo "   sudo thatd build     # Build development containers"
echo "   sudo thatd deploy    # Deploy development environment"
echo ""
echo "📁 Environment locations:"
echo "   Production:  $PROD_DIR"
echo "   Development: $DEV_DIR"
echo ""