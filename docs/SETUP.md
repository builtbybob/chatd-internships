# Ch@d Internships Bot - Complete Setup Guide

This guide covers the complete setup process for the ChatD Internships Discord bot using Docker Compose with PostgreSQL database and systemd for production deployment.

## Overview

The ChatD Internships bot monitors the [Summer2026-Internships](https://github.com/SimplifyJobs/Summer2026-Internships) repository for new job postings and posts updates to Discord channels. The bot uses:

- **Docker Compose** for containerized deployment
- **PostgreSQL** database for job posting and message tracking data
- **systemd** for automatic startup and service management
- **Management scripts** for easy administration

## Prerequisites

Before starting, ensure you have:

- **Linux system** (tested on Ubuntu/Debian/Raspberry Pi OS)
- **Docker and Docker Compose** installed
- **Git** installed
- **Discord bot token** and **channel IDs**
- **Root/sudo access** for system configuration

## Step 1: System Preparation

### Install Required Packages

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y git docker.io docker-compose curl

# Add current user to docker group
sudo usermod -aG docker $USER

# Log out and back in (or reboot) to apply group changes
sudo reboot
```

### Verify Docker Installation

```bash
# Test Docker installation
docker --version
docker-compose --version
docker run hello-world
```

## Step 2: Clone Repository and Setup Working Directory

### Clone the Ch@d Repository

```bash
# Clone to a temporary location first
cd ~
git clone https://github.com/builtbybob/chatd-internships.git
cd chatd-internships
```

### Setup Production Directory

The bot runs from `/opt/chatd/` with the following structure:

```bash
# Create the production directory and copy files
sudo mkdir -p /opt/chatd
sudo cp -r . /opt/chatd/
cd /opt/chatd

# Create required data directories
sudo mkdir -p /opt/chatd/data /opt/chatd/logs

# Set proper ownership (Docker containers run as user 1000)
sudo chown -R 1000:1000 /opt/chatd/data /opt/chatd/logs
```

### Clone the Internships Repository

```bash
# Clone the internships repository that the bot monitors
cd /opt/chatd
sudo git clone https://github.com/SimplifyJobs/Summer2026-Internships.git

# Set proper ownership
sudo chown -R 1000:1000 /opt/chatd/Summer2026-Internships
```

## Step 3: Discord Bot Configuration

### Create Environment Configuration

```bash
# Copy the example configuration
cd /opt/chatd
sudo cp .env.example .env

# Set secure permissions (contains Discord token)
sudo chmod 600 .env

# Edit configuration
sudo nano .env
```

### Configure Environment Variables

Edit `/opt/chatd/.env` with your settings:

```ini
###############################################################
# Discord Bot Configuration (MANDATORY)
###############################################################

# Your Discord bot token (get from Discord Developer Portal)
DISCORD_TOKEN=your_discord_bot_token_here

# Comma-separated list of Discord channel IDs to post to
CHANNEL_IDS=123456789012345678,987654321098765432

###############################################################
# Database Configuration (MANDATORY)
###############################################################

# Database password for PostgreSQL (generate a secure password)
DB_PASSWORD=your_secure_postgres_password_here

# Database migration mode: json_only|dual_write|database_only
MIGRATION_MODE=database_only

###############################################################
# Logging Configuration
###############################################################

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

###############################################################
# Bot Behavior
###############################################################

# Enable reactions on posted messages (true/false)
ENABLE_REACTIONS=false

# Maximum number of retries for failed operations
MAX_RETRIES=3

# How often to check for new job postings (minutes)
CHECK_INTERVAL_MINUTES=1

# Maximum age of job postings to display (days)
MAX_POST_AGE_DAYS=3
```

**Required Settings:**

1. **`DISCORD_TOKEN`**: Get from [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to Bot section
   - Copy the token

2. **`CHANNEL_IDS`**: Discord channel IDs where bot should post (comma-separated)
   - Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
   - Right-click on channel → Copy ID

3. **`DB_PASSWORD`**: Generate a secure password for PostgreSQL:
   ```bash
   # Generate a secure password
   openssl rand -base64 32
   ```

## Step 4: Database Setup (PostgreSQL)

The bot uses PostgreSQL for storing job postings and tracking sent messages. The database is automatically configured with Docker Compose.

### Start PostgreSQL Container

```bash
cd /opt/chatd

# Start only the PostgreSQL container first
sudo docker-compose up -d chatd-postgres

# Wait for database to be ready (may take 30-60 seconds)
echo "Waiting for PostgreSQL to initialize..."
sleep 30

# Verify database is ready
sudo docker exec chatd-postgres pg_isready -U chatd
# Expected output: /var/run/postgresql:5432 - accepting connections
```

### Verify Database Schema

The database schema is automatically created from `sql/init/001_initial_schema.sql`:

```bash
# Check container status
sudo docker ps | grep chatd-postgres

# Verify database tables were created
sudo docker exec -it chatd-postgres psql -U chatd -d chatd -c "\dt"

# Expected tables:
# - job_postings      (main job data)
# - job_locations     (job locations)
# - job_terms         (job terms like "Summer 2026")
# - job_degrees       (degree requirements)
# - message_tracking  (tracks sent Discord messages)

# Test the readable view
sudo docker exec -it chatd-postgres psql -U chatd -d chatd -c "SELECT * FROM job_postings_readable LIMIT 1;"
```

## Step 5: Initial Data Sync

**CRITICAL STEP**: Prevent the bot from replaying old messages by syncing current repository state:

```bash
cd /opt/chatd

# Use the sync script to set baseline
sudo ./scripts/sync-repo-data.sh

# This script:
# - Copies current listings.json to previous_data.json
# - Clears message tracking
# - Ensures no old messages are replayed on first run
```

## Step 6: Install Management Scripts

### Create Management Commands

```bash
cd /opt/chatd

# Install management scripts
sudo ./scripts/create-management-scripts.sh

# This creates commands like:
# - chatd (main control)
# - chatd-logs (log viewer)
# - chatd-loglevel (dynamic log control)
# - chatd-build, chatd-deploy, chatd-update
```

### Install Systemd Service

```bash
# Copy systemd service file
sudo cp chatd-internships.service /etc/systemd/system/

# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable chatd-internships
```

## Step 7: Build and Deploy

### Build Docker Images

```bash
cd /opt/chatd

# Build the bot Docker image
sudo chatd build

# This builds the chatd-bot container with current code
```

### Start the Complete Service

```bash
# Start both PostgreSQL and bot containers
sudo systemctl start chatd-internships

# Check service status
sudo chatd status
```

### Verify Operation

```bash
# Monitor logs in real-time
sudo chatd logs -f

# Check for successful startup messages:
# ✅ Logging configured with level: INFO
# ✅ Configuration validation completed successfully
# ✅ Database connection successful (PostgreSQL)
# ✅ Discord connection successful (logged in as YourBot#1234)
# ✅ Can access 1/1 configured channels
# 🔍 No updates to listings file, skipping check
```

The message "No updates to listings file, skipping check" confirms that message replay prevention worked correctly.

## Step 8: Management and Monitoring

### Service Management

```bash
# Check overall status
sudo chatd status

# View logs
sudo chatd logs -f              # Follow logs in real-time
sudo chatd logs -n 100          # Show last 100 lines

# Service control
sudo systemctl start chatd-internships
sudo systemctl stop chatd-internships
sudo systemctl restart chatd-internships

# Enable/disable auto-start on boot
sudo systemctl enable chatd-internships
sudo systemctl disable chatd-internships
```

### Dynamic Log Level Control

```bash
# Enable debug logging for troubleshooting
sudo chatd-loglevel debug

# Return to normal logging
sudo chatd-loglevel info

# Other levels: warning, error, critical
```

### Docker Container Management

```bash
# Check container status
sudo docker ps

# View container-specific logs
sudo docker logs chatd-bot
sudo docker logs chatd-postgres

# Restart specific containers
sudo docker restart chatd-bot
sudo docker restart chatd-postgres
```

### Database Management

```bash
# Connect to database for inspection
sudo docker exec -it chatd-postgres psql -U chatd -d chatd

# Common database queries:
# \dt                                    # List tables
# \dv                                    # List views
# SELECT COUNT(*) FROM job_postings;     # Count job postings
# SELECT COUNT(*) FROM message_tracking; # Count tracked messages
# \q                                     # Quit psql

# Database backup
sudo docker exec chatd-postgres pg_dump -U chatd chatd > /opt/chatd/data/backup_$(date +%Y%m%d_%H%M%S).sql
```

### Repository Synchronization

```bash
# Sync to latest repository version
sudo ./scripts/sync-repo-data.sh

# Sync to specific commit (useful for testing)
sudo ./scripts/sync-repo-data.sh abc123def456
```

## Step 9: Updates and Maintenance

### Updating the Bot

```bash
# Update to latest code and redeploy
sudo chatd update

# Update to specific branch
sudo chatd update dev

# Manual update process:
cd /opt/chatd
sudo git pull
sudo chatd build
sudo chatd deploy
```

### Database Migration (From JSON to PostgreSQL)

If upgrading from a JSON-only installation:

```bash
cd /opt/chatd

# Ensure PostgreSQL is running
sudo docker ps | grep chatd-postgres

# Run migration with dry-run to preview
python3 scripts/migrate_json_to_database.py --dry-run --verbose

# Execute the actual migration
python3 scripts/migrate_json_to_database.py --verbose

# Update configuration to use database only
sudo nano .env
# Change: MIGRATION_MODE=database_only

# Restart service
sudo systemctl restart chatd-internships
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check service status for errors
sudo systemctl status chatd-internships

# Check Docker logs
sudo docker logs chatd-bot
sudo docker logs chatd-postgres

# Common fixes:
sudo systemctl daemon-reload
sudo systemctl restart chatd-internships

# Check if containers are running
sudo docker ps -a
```

#### 2. Database Connection Issues

```bash
# Check PostgreSQL container status
sudo docker ps | grep chatd-postgres

# Check database connectivity
sudo docker exec chatd-postgres pg_isready -U chatd

# View database logs
sudo docker logs chatd-postgres

# Restart database container
sudo docker restart chatd-postgres

# Check environment variables
sudo grep DB_ /opt/chatd/.env
```

#### 3. Permission Errors

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 /opt/chatd/data /opt/chatd/logs /opt/chatd/Summer2026-Internships

# Fix configuration permissions
sudo chmod 600 /opt/chatd/.env

# Check Docker group membership
groups $USER
# Should include 'docker'
```

#### 4. Discord Connection Issues

```bash
# Verify Discord token in configuration
sudo grep DISCORD_TOKEN /opt/chatd/.env

# Check channel IDs format
sudo grep CHANNEL_IDS /opt/chatd/.env

# Test with debug logging
sudo chatd-loglevel debug
sudo chatd logs -f
```

#### 5. Repository Issues

```bash
# Check repository structure
ls -la /opt/chatd/Summer2026-Internships/
# Should show: .git/, .github/, README.md

# Check if repository is accessible
cd /opt/chatd/Summer2026-Internships
sudo git status
sudo git pull

# Re-sync repository data
sudo ./scripts/sync-repo-data.sh
```

#### 6. Container Issues

```bash
# Check Docker service
sudo systemctl status docker

# Restart Docker service
sudo systemctl restart docker

# Clean up containers and rebuild
sudo docker-compose down
sudo docker system prune -f
sudo chatd build
sudo systemctl start chatd-internships
```

### Log Analysis

#### Successful Startup Sequence

```
[2025-10-03 13:36:45 INFO __main__:21] 🚀 Starting ChatD Internships Bot...
[2025-10-03 13:36:45 INFO __main__:25] 🔧 Validating configuration...
[2025-10-03 13:36:45 INFO chatd.config:184] ✅ Configuration validation passed.
[2025-10-03 13:36:45 INFO __main__:32] ✅ Configuration validation completed successfully
[2025-10-03 13:36:45 INFO __main__:39] 🤖 Starting Discord bot...
[2025-10-03 13:36:45 INFO chatd.database:75] Database connection successful (PostgreSQL)
[2025-10-03 13:36:45 INFO chatd.bot:413] Starting bot with environment configuration...
[2025-10-03 13:36:45 INFO discord.client:611] logging in using static token
[2025-10-03 13:36:46 INFO chatd.bot:327] Logged in as YourBot#1234
[2025-10-03 13:36:46 INFO chatd.bot:328] Bot is ready and monitoring 1 channels
```

#### Warning Signs

```bash
# Discord token issues:
❌ Discord login failed - invalid token

# Database issues:
❌ Database connection failed
❌ Database health check failed

# Configuration issues:
❌ Missing required environment variables
❌ Cannot access repository

# Permission issues:
OSError: [Errno 13] Permission denied
```

### Emergency Recovery

```bash
# Complete reset (nuclear option)
sudo systemctl stop chatd-internships
sudo docker-compose down
sudo docker system prune -f
sudo rm -rf /opt/chatd/data/*
sudo ./scripts/sync-repo-data.sh
sudo systemctl start chatd-internships
```

## File Structure Reference

After successful setup, your system should have:

```
/opt/chatd/                              # Main working directory
├── .env                                 # Environment configuration
├── docker-compose.yml                   # Container orchestration
├── chatd-internships.service            # Systemd service definition
├── Dockerfile                           # Bot container build
├── requirements.txt                     # Python dependencies
├── main.py                             # Bot entry point
├── chatd/                              # Bot source code
│   ├── __init__.py
│   ├── bot.py                          # Discord bot logic
│   ├── config.py                       # Configuration management
│   ├── database.py                     # PostgreSQL integration
│   ├── logging_utils.py                # Logging configuration
│   ├── messages.py                     # Message formatting
│   ├── repo.py                         # Git repository handling
│   ├── storage.py                      # Data storage (legacy JSON)
│   └── storage_abstraction.py          # Storage interface
├── sql/                                # Database schema
│   └── init/
│       └── 001_initial_schema.sql      # PostgreSQL schema
├── scripts/                            # Management scripts
│   ├── create-management-scripts.sh    # Installs admin commands
│   ├── sync-repo-data.sh              # Repository sync utility
│   └── migrate_json_to_database.py    # Migration script
├── data/                               # Application data
│   ├── previous_data.json              # Baseline job listings
│   ├── message_tracking.json           # Message tracking (JSON mode)
│   └── current_head.txt               # Git commit tracking
├── logs/                               # Application logs
│   └── chatd.log                      # Main log file
└── Summer2026-Internships/             # Monitored repository
    ├── .git/
    ├── .github/
    │   └── scripts/
    │       └── listings.json           # Current job listings
    └── README.md

# Docker Components
Docker Containers:
├── chatd-bot                           # Main bot container
└── chatd-postgres                      # PostgreSQL database

Docker Volumes:
└── postgres_data                       # Persistent database storage

# System Integration
/etc/systemd/system/
└── chatd-internships.service          # Systemd service

/usr/local/bin/
├── chatd                              # Main management command
├── chatd-build                        # Build Docker image
├── chatd-deploy                       # Deploy existing image
├── chatd-update                       # Build and deploy
├── chatd-logs                         # Log viewer
├── chatd-loglevel                     # Dynamic log control
├── chatd-version                      # Version management
├── chatd-backup                       # Backup utility
├── chatd-cleanup                      # Image cleanup
└── chatd-data                         # Data inspection
```

## Security Considerations

1. **Environment File Security**
   ```bash
   # Secure the configuration file (contains Discord token and DB password)
   sudo chmod 600 /opt/chatd/.env
   ```

2. **Database Security**
   - Database is only accessible within Docker network
   - Strong password required for database access
   - Regular security updates via `sudo apt update && sudo apt upgrade`

3. **Network Security**
   - Bot only makes outbound connections (GitHub API, Discord API)
   - No inbound ports needed for bot operation
   - PostgreSQL port (5432) exposed only for development (remove in production)

4. **System Updates**
   ```bash
   # Keep system updated
   sudo apt update && sudo apt upgrade -y
   
   # Update Docker images periodically
   sudo docker pull postgres:15-alpine
   sudo chatd build
   ```

## Performance Notes

- **Memory Usage**: ~100-200MB total (bot: ~50-100MB, PostgreSQL: ~50-100MB)
- **Disk Usage**: ~500MB for images + variable for data
- **CPU Usage**: Minimal (periodic git pulls and Discord API calls)
- **Network**: Outbound HTTPS only (GitHub API, Discord API)
- **Database**: Optimized with indexes for common query patterns

## Production Recommendations

1. **Monitoring Setup**
   ```bash
   # Set up log rotation
   sudo nano /etc/logrotate.d/chatd
   ```

2. **Backup Strategy**
   ```bash
   # Regular database backups
   sudo crontab -e
   # Add: 0 2 * * * docker exec chatd-postgres pg_dump -U chatd chatd > /opt/chatd/data/backup_$(date +\%Y\%m\%d).sql
   ```

3. **Resource Limits**
   - Consider setting Docker memory limits for production
   - Monitor disk usage for log files and database growth

4. **High Availability**
   - Set up external database for multi-instance deployments
   - Use Docker Swarm or Kubernetes for scaling

## Next Steps

After successful setup:

1. **Monitor Initial Operation**: Watch logs for 24 hours to ensure stability
2. **Set Up Monitoring**: Consider setting up alerts for service failures
3. **Configure Backups**: Set up regular backups of database and configuration
4. **Performance Tuning**: Monitor resource usage and adjust as needed
5. **Update Procedures**: Establish regular update schedule for security

The ChatD Internships bot is now ready for production use! 🚀

For support, issues, or contributions, visit: https://github.com/builtbybob/chatd-internships

---

## Development Environment Setup

This section covers setting up a local development environment that runs in parallel with your production deployment, allowing you to test changes safely without disrupting the live bot.

### Overview

The development setup uses:
- **Separate Discord bot** (e.g., "ThatdInternships") 
- **Isolated database** (chatd_test vs chatd)
- **Different container names** to avoid conflicts
- **Different ports** to prevent collisions
- **Local directory** instead of `/opt/chatd/`

### Prerequisites

- Production ChatD bot already running via systemctl
- Separate Discord bot created for testing
- Access to test Discord channels
- Development working in `/home/user/chatd-internships/`

### Step 1: Create Test Bot on Discord

1. **Create New Application**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" 
   - Name it "ThatdInternships" (or similar)

2. **Configure Bot**:
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the bot token (you'll need this)
   - Enable necessary intents if required

3. **Add to Test Server**:
   - Go to "OAuth2" → "URL Generator"
   - Select "bot" scope
   - Select necessary permissions (Send Messages, Add Reactions, etc.)
   - Use generated URL to add bot to your test server

4. **Get Test Channel IDs**:
   - In Discord, enable Developer Mode (User Settings → Advanced → Developer Mode)
   - Right-click test channels → Copy ID

### Step 2: Copy and Configure Environment

```bash
# From your development directory
cd /home/rbarton/chatd-internships

# Copy production environment as starting point
sudo cp /opt/chatd/.env .env.test

# Edit the test configuration
nano .env.test
```

**Configure `.env.test` with test-specific values:**

```ini
###############################################################
# Discord Bot Configuration (TEST BOT)
###############################################################

# Your TEST Discord bot token (different from production)
DISCORD_TOKEN=your_test_bot_token_here

# Test Discord channel IDs (comma-separated)
CHANNEL_IDS=your_test_channel_ids_here

###############################################################
# Database Configuration (TEST DATABASE)
###############################################################

# Test database password (can be different from production)
DB_PASSWORD=test_chatd_password_123

# Use database-only mode for testing
MIGRATION_MODE=database_only

###############################################################
# Development/Testing Configuration
###############################################################

# Enable debug logging for development
LOG_LEVEL=DEBUG

# Enable reactions for testing reaction features
ENABLE_REACTIONS=true

# Faster check interval for development testing
CHECK_INTERVAL_MINUTES=1

# Standard settings
MAX_RETRIES=3
MAX_POST_AGE_DAYS=3
```

### Step 3: Create Development Docker Compose

Create a `docker-compose.test.yml` file for your development environment:

```bash
# Create test docker-compose file
cat > docker-compose.test.yml << 'EOF'
version: '3.8'
services:
  chatd-postgres-test:
    image: postgres:15-alpine
    container_name: chatd-postgres-test
    environment:
      POSTGRES_DB: chatd_test
      POSTGRES_USER: chatd
      POSTGRES_PASSWORD: ${DB_PASSWORD:-test_chatd_password_123}
    volumes:
      - postgres_test_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d:ro
    ports:
      # Use different port to avoid conflict with production
      - "5433:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chatd -d chatd_test"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - chatd-test-network

  chatd-bot-test:
    build: .
    container_name: chatd-bot-test
    environment:
      # Load from test environment file
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - CHANNEL_IDS=${CHANNEL_IDS}
      - DB_PASSWORD=${DB_PASSWORD}
      - MIGRATION_MODE=${MIGRATION_MODE:-database_only}
      - LOG_LEVEL=${LOG_LEVEL:-DEBUG}
      - ENABLE_REACTIONS=${ENABLE_REACTIONS:-true}
      - MAX_POST_AGE_DAYS=${MAX_POST_AGE_DAYS:-3}
      - CHECK_INTERVAL_MINUTES=${CHECK_INTERVAL_MINUTES:-1}
      - MAX_RETRIES=${MAX_RETRIES:-3}
      # Test database configuration
      - DB_HOST=chatd-postgres-test
      - DB_PORT=5432
      - DB_NAME=chatd_test
      - DB_USER=chatd
      - DB_TYPE=postgresql
      # Timezone configuration
      - TZ=${TZ:-UTC}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./Summer2026-Internships:/app/Summer2026-Internships
      # Mount timezone data
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
    depends_on:
      chatd-postgres-test:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - chatd-test-network
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f python3 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

volumes:
  postgres_test_data:
    driver: local

networks:
  chatd-test-network:
    driver: bridge
EOF
```

### Step 4: Prepare Development Data

```bash
# Ensure Summer2026-Internships repository exists locally
if [ ! -d "Summer2026-Internships" ]; then
    git clone https://github.com/SimplifyJobs/Summer2026-Internships.git
fi

# Create local data and logs directories
mkdir -p data logs

# Set proper permissions for Docker containers
sudo chown -R 1000:1000 data logs Summer2026-Internships

# Sync current repository state to prevent replaying old messages
cp Summer2026-Internships/.github/scripts/listings.json data/previous_data.json

# Create empty message tracking file
echo '{}' > data/message_tracking.json

# Create current head tracking file
cd Summer2026-Internships
git rev-parse HEAD > ../data/current_head.txt
cd ..
```

### Step 5: Start Development Environment

```bash
# Load test environment variables
export $(cat .env.test | xargs)

# Start test environment with test compose file
docker-compose -f docker-compose.test.yml up -d

# Wait for database to initialize
echo "Waiting for test database to initialize..."
sleep 30

# Check container status
docker ps | grep test

# Expected output should show:
# chatd-postgres-test
# chatd-bot-test
```

### Step 6: Verify Development Environment

```bash
# Check container logs
docker-compose -f docker-compose.test.yml logs chatd-bot-test

# Should see successful startup messages:
# ✅ Configuration validation passed
# ✅ Database connection successful (PostgreSQL)  
# ✅ Discord connection successful (logged in as ThatdInternships#1234)
# ✅ Can access X/X configured channels

# Test database connection
docker exec -it chatd-postgres-test psql -U chatd -d chatd_test -c "\dt"

# Should show the same table structure as production:
# job_postings, job_locations, job_terms, job_degrees, message_tracking
```

### Step 7: Development Workflow

#### Making and Testing Changes

```bash
# 1. Make code changes to chatd/*.py files
nano chatd/bot.py

# 2. Rebuild and restart test bot
docker-compose -f docker-compose.test.yml build chatd-bot-test
docker-compose -f docker-compose.test.yml restart chatd-bot-test

# 3. Monitor test logs
docker-compose -f docker-compose.test.yml logs -f chatd-bot-test
```

#### Testing New Features

```bash
# Enable debug logging to see detailed operation
docker exec -it chatd-bot-test python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
"

# Test specific reactions or features in your test Discord channels
# Your test bot will operate independently of production
```

#### Database Inspection

```bash
# Connect to test database
docker exec -it chatd-postgres-test psql -U chatd -d chatd_test

# Useful queries for development:
# SELECT COUNT(*) FROM job_postings;
# SELECT * FROM message_tracking ORDER BY posted_at DESC LIMIT 5;
# SELECT company_name, COUNT(*) FROM job_postings GROUP BY company_name ORDER BY count DESC LIMIT 10;
```

### Step 8: Managing Development Environment

#### Start/Stop Development Environment

```bash
# Start development environment
docker-compose -f docker-compose.test.yml up -d

# Stop development environment  
docker-compose -f docker-compose.test.yml down

# Stop and remove volumes (fresh start)
docker-compose -f docker-compose.test.yml down -v
```

#### View Logs

```bash
# Follow all logs
docker-compose -f docker-compose.test.yml logs -f

# Follow just bot logs
docker-compose -f docker-compose.test.yml logs -f chatd-bot-test

# Follow just database logs
docker-compose -f docker-compose.test.yml logs -f chatd-postgres-test

# View recent logs
docker-compose -f docker-compose.test.yml logs --tail=100 chatd-bot-test
```

#### Reset Development Environment

```bash
# Complete reset (clean slate)
docker-compose -f docker-compose.test.yml down -v
docker system prune -f
rm -rf data/* logs/*

# Re-sync repository data
cp Summer2026-Internships/.github/scripts/listings.json data/previous_data.json
echo '{}' > data/message_tracking.json
cd Summer2026-Internships && git rev-parse HEAD > ../data/current_head.txt && cd ..

# Restart
docker-compose -f docker-compose.test.yml up -d
```

### Key Differences from Production

| Aspect | Production | Development |
|--------|------------|-------------|
| **Service Management** | systemctl | docker-compose |
| **Working Directory** | `/opt/chatd/` | `./` (current dir) |
| **Discord Bot** | ChatD#1234 | ThatdInternships#5678 |
| **Database** | `chatd` | `chatd_test` |
| **Database Port** | 5432 (internal) | 5433 (host accessible) |
| **Container Names** | chatd-bot, chatd-postgres | chatd-bot-test, chatd-postgres-test |
| **Log Level** | INFO | DEBUG |
| **Reactions** | Disabled | Enabled for testing |
| **Auto-restart** | systemctl managed | docker-compose restart policy |

### Troubleshooting Development Setup

#### Port Conflicts

```bash
# Check if ports are in use
sudo netstat -tlnp | grep :5433

# If port 5433 is busy, change it in docker-compose.test.yml:
# ports:
#   - "5434:5432"  # Use different port
```

#### Container Name Conflicts

```bash
# Check for existing containers
docker ps -a | grep chatd

# If containers exist with same names, either:
# 1. Use different names in docker-compose.test.yml
# 2. Stop/remove conflicting containers:
docker stop chatd-bot-test chatd-postgres-test
docker rm chatd-bot-test chatd-postgres-test
```

#### Environment Variable Issues

```bash
# Verify environment file is loaded correctly
docker exec chatd-bot-test env | grep DISCORD

# Check for missing variables
docker-compose -f docker-compose.test.yml config
```

#### Database Connection Issues

```bash
# Check if test database is running
docker ps | grep postgres-test

# Test database connectivity
docker exec chatd-postgres-test pg_isready -U chatd -d chatd_test

# Check database logs
docker logs chatd-postgres-test
```

#### Bot Connection Issues

```bash
# Verify Discord token is correct for test bot
echo $DISCORD_TOKEN

# Check channel IDs are correct for test channels  
echo $CHANNEL_IDS

# Verify test bot has permissions in test channels
# Check Discord bot OAuth2 permissions
```

### Development Best Practices

1. **Keep Environments Isolated**:
   - Never use production Discord tokens in development
   - Use separate test channels
   - Don't share databases between environments

2. **Regular Cleanup**:
   ```bash
   # Clean up development containers and images regularly
   docker-compose -f docker-compose.test.yml down
   docker system prune -f
   ```

3. **Test Thoroughly**:
   - Test new features in development first
   - Verify database migrations work correctly
   - Test error handling and edge cases

4. **Monitor Resource Usage**:
   ```bash
   # Check Docker resource usage
   docker stats
   
   # Monitor disk usage
   df -h
   docker system df
   ```

5. **Version Control**:
   - Don't commit `.env.test` (contains tokens)
   - Use `.gitignore` to exclude sensitive files
   - Keep `docker-compose.test.yml` in version control

### Integration with Production

When your development changes are ready:

1. **Test thoroughly** in development environment
2. **Create feature branch** for changes
3. **Deploy to production** using standard update process:
   ```bash
   # On production system
   cd /opt/chatd
   sudo git pull
   sudo chatd update
   ```

The development environment allows you to safely test new features, debug issues, and experiment with configurations without any risk to your production Discord bot! 🚀