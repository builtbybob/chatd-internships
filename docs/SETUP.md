# ChatD Internships Bot - Initial Setup Guide

This guide covers the complete setup process for the ChatD Internships Discord bot using Docker and systemd for production deployment.

## Prerequisites

Before starting, ensure you have:

- **Linux system** (tested on Ubuntu/Debian/Raspberry Pi OS)
- **Docker** installed and running
- **Git** installed
- **Discord bot token** and **channel IDs**
- **Root/sudo access** for system configuration

## Step 1: System Preparation

### Install Required Packages

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y git docker.io curl docker-compose

# Add current user to docker group
sudo usermod -aG docker $USER

# Restart to apply group changes (or logout/login)
sudo reboot
```

### Verify Docker Installation

```bash
# Test Docker installation
docker --version
docker run hello-world
```

## Step 2: Clone and Setup Repository

### Clone the Repository

```bash
# Clone to your home directory or preferred location
cd ~
git clone https://github.com/builtbybob/chatd-internships.git
cd chatd-internships
```

### Create System Directories

```bash
# Create required directories with correct permissions
sudo mkdir -p /var/lib/chatd/data /var/lib/chatd/repo /var/lib/chatd/logs
sudo chown -R 1000:1000 /var/lib/chatd/
```

## Step 3: Database Setup (PostgreSQL)

The ChatD bot supports both JSON file storage (legacy) and PostgreSQL database storage. PostgreSQL provides better data integrity, querying capabilities, and scalability.

### Option A: PostgreSQL Database (Recommended)

#### Setup PostgreSQL with Docker

```bash
# Navigate to the repository
cd ~/chatd-internships

# Generate a secure database password
POSTGRES_PASSWORD=$(openssl rand -base64 32)
echo "Generated PostgreSQL password: $POSTGRES_PASSWORD"

# Create PostgreSQL environment file
sudo mkdir -p /etc/chatd
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" | sudo tee /etc/chatd/.env.postgres
sudo chmod 600 /etc/chatd/.env.postgres

# Start PostgreSQL container
docker compose -f docker-compose.database.yml up -d

# Wait for database to be ready (may take 30-60 seconds)
echo "Waiting for PostgreSQL to be ready..."
sleep 30

# Verify database connection
docker exec chatd-postgres pg_isready -U chatd
```

#### Verify Database Setup

```bash
# Check container status
docker ps | grep chatd-postgres

# Test database connection and schema
docker exec -it chatd-postgres psql -U chatd -d chatd -c "\dt"

# You should see the following tables:
# - job_postings
# - job_locations  
# - job_terms
# - message_tracking
# - jobs_with_details (view)
```

#### Database Migration Options

The bot supports three migration modes:

1. **`json_only`** - Legacy JSON file storage (default)
2. **`dual_write`** - Write to both JSON and database (migration phase)
3. **`database_only`** - PostgreSQL only (recommended for new deployments)

### Option B: JSON File Storage (Legacy)

If you prefer to use JSON file storage or are upgrading an existing installation, you can skip the database setup and use the default configuration.

## Step 4: Discord Bot Configuration

### Create Configuration File

```bash
# Create configuration directory
sudo mkdir -p /etc/chatd

# Copy example configuration
sudo cp .env.example /etc/chatd/.env

# Set secure permissions
sudo chmod 600 /etc/chatd/.env

# Edit configuration
sudo nano /etc/chatd/.env
```

### Configure Environment Variables

Edit `/etc/chatd/.env` with your settings:

```ini
# Discord Bot Configuration (REQUIRED)
DISCORD_TOKEN=your_discord_bot_token_here
CHANNEL_IDS=123456789012345678,987654321098765432

# Database Configuration (PostgreSQL)
DB_TYPE=postgresql
DB_HOST=chatd-postgres
DB_PORT=5432
DB_NAME=chatd
DB_USER=chatd
DB_PASSWORD=your_postgres_password_from_step_3

# Migration Mode (choose one)
MIGRATION_MODE=database_only      # For new installations with PostgreSQL
# MIGRATION_MODE=json_only        # For legacy JSON file storage
# MIGRATION_MODE=dual_write       # For gradual migration from JSON to PostgreSQL

# Logging Configuration
LOG_LEVEL=INFO

# Bot Behavior
ENABLE_REACTIONS=false
MAX_RETRIES=3
CHECK_INTERVAL_MINUTES=1
MAX_POST_AGE_DAYS=5

# Repository Settings (usually don't need to change)
REPO_URL=https://github.com/SimplifyJobs/Summer2026-Internships.git
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

**Required Settings:**
- `DISCORD_TOKEN`: Your Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications)
- `CHANNEL_IDS`: Comma-separated list of Discord channel IDs where the bot should send messages

**Database Settings (if using PostgreSQL):**
- `DB_PASSWORD`: Use the password generated in Step 3 (found in `/etc/chatd/.env.postgres`)
- `MIGRATION_MODE`: Choose based on your setup:
  - `database_only`: New installations with PostgreSQL (recommended)
  - `json_only`: Legacy JSON file storage
  - `dual_write`: Migration phase (writes to both JSON and database)

**How to get Discord Channel ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click on the channel → Copy ID

**How to get Database Password:**
```bash
# View the generated PostgreSQL password
sudo cat /etc/chatd/.env.postgres
```

## Step 5: Repository Data Setup

### Initial Repository Clone

```bash
# Clone the internships repository directly to the correct location
cd /var/lib/chatd/
sudo git clone https://github.com/SimplifyJobs/Summer2026-Internships.git repo

# Set correct ownership
sudo chown -R 1000:1000 /var/lib/chatd/repo/

# Note: If you later encounter "Permission denied" errors on .git/FETCH_HEAD,
# re-run the chown command above to fix git repository permissions
```

### Prevent Message Replay

**CRITICAL STEP**: To prevent the bot from replaying old messages, sync the current repository state:

```bash
# Use the provided sync script to set baseline
cd ~/chatd-internships
sudo ./scripts/sync-repo-data.sh
```

This script:
- Copies current `listings.json` to `previous_data.json`
- Clears message tracking
- Ensures no old messages are replayed on first run

### Database Migration (Optional - For Existing Installations)

If you have an existing installation with JSON data and want to migrate to PostgreSQL:

```bash
# Step 1: Ensure PostgreSQL is running
docker ps | grep chatd-postgres

# Step 2: Run migration with dry-run to preview
cd ~/chatd-internships
python scripts/migrate_json_to_database.py --dry-run --verbose

# Step 3: Execute the actual migration
python scripts/migrate_json_to_database.py --verify

# Step 4: Update configuration to use database
sudo nano /etc/chatd/.env
# Change: MIGRATION_MODE=database_only
```

The migration script will:
- Create automatic backups of your JSON files
- Validate all data before migration
- Import historical job postings and message tracking
- Verify data integrity after migration

## Step 6: Install Management Scripts

### Install System Integration

```bash
# Install management scripts and systemd service
cd ~/chatd-internships
sudo ./scripts/create-management-scripts.sh
```

This creates:
- Management commands (`chatd`, `chatd-logs`, `chatd-loglevel`)
- Systemd service file
- Docker integration

### Copy Service File

```bash
# Copy systemd service file
sudo cp chatd-internships.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable chatd-internships
```

## Step 7: Build and Deploy

### Build Docker Image

```bash
# Build the bot's Docker image
sudo chatd build
```

### Start the Service

```bash
# Start the bot service
sudo systemctl start chatd-internships

# Check service status
chatd status
```

### Verify Operation

```bash
# Monitor logs in real-time
chatd logs -f

# Check for successful startup messages:
# ✅ Configuration validation completed successfully
# ✅ Discord connection successful
# 🔍 No updates to listings file, skipping check
```

The message "No updates to listings file, skipping check" confirms that message replay prevention worked correctly.

## Step 8: Management and Monitoring

### Service Management

```bash
# Check service status
chatd status

# View logs
chatd logs -f              # Follow logs in real-time
chatd logs -n 100          # Show last 100 lines

# Service control
sudo systemctl start chatd-internships
sudo systemctl stop chatd-internships
sudo systemctl restart chatd-internships
```

### Dynamic Log Level Control

```bash
# Enable debug logging for troubleshooting
sudo chatd-loglevel debug

# Return to normal logging
sudo chatd-loglevel info

# Other levels: warning, error, critical
```

### Repository Synchronization

```bash
# Sync to latest repository version
sudo ./scripts/sync-repo-data.sh

# Sync to specific commit (useful for testing)
sudo ./scripts/sync-repo-data.sh abc123def456
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start
```bash
# Check service status for errors
sudo systemctl status chatd-internships

# Check Docker logs
docker logs chatd-bot

# Common fixes:
sudo systemctl daemon-reload
sudo systemctl restart chatd-internships
```

#### 2. Permission Errors
```bash
# Fix data directory permissions
sudo chown -R 1000:1000 /var/lib/chatd/

# Fix configuration permissions
sudo chmod 600 /etc/chatd/.env
```

#### 3. Repository Issues
```bash
# Check repository structure
ls -la /var/lib/chatd/repo/
# Should show: .git/, .github/, README.md (not nested Summer2026-Internships/)

# Re-sync repository data
sudo ./scripts/sync-repo-data.sh
```

#### 4. Database Issues (PostgreSQL)
```bash
# Check PostgreSQL container status
docker ps | grep chatd-postgres

# Check database connectivity
docker exec chatd-postgres pg_isready -U chatd

# View database logs
docker logs chatd-postgres

# Restart database container
docker restart chatd-postgres

# Connect to database for manual inspection
docker exec -it chatd-postgres psql -U chatd -d chatd

# Common database commands:
# \dt                           # List tables
# SELECT COUNT(*) FROM job_postings;  # Count records
# \q                            # Quit psql
```

#### 5. Database Migration Issues
```bash
# Check migration status
python scripts/migrate_json_to_database.py --dry-run

# View migration logs for errors
cat /var/lib/chatd/logs/chatd.log | grep -i migration

# Rollback to JSON mode if needed
sudo nano /etc/chatd/.env
# Change: MIGRATION_MODE=json_only
sudo systemctl restart chatd-internships
```

#### 6. Bot Replays Old Messages
```bash
# Stop service and re-sync data
sudo systemctl stop chatd-internships
sudo ./scripts/sync-repo-data.sh
sudo systemctl start chatd-internships
```

#### 7. Docker Issues
```bash
# Restart Docker service
sudo systemctl restart docker

# Rebuild bot image
sudo chatd build

# Check Docker status
docker ps -a
```

### Log Analysis

#### Successful Startup Logs

**With PostgreSQL Database:**
```
✅ Configuration validation completed successfully
✅ Database connection successful (PostgreSQL)
✅ Database health check passed
✅ Discord connection successful (logged in as YourBot#1234)
✅ Can access 1/1 configured channels
📡 Pulling latest changes from git...
🔍 No updates to listings file, skipping check
```

**With JSON Storage:**
```
✅ Configuration validation completed successfully
✅ Discord connection successful (logged in as YourBot#1234)
✅ Can access 1/1 configured channels
📡 Pulling latest changes from git...
🔍 No updates to listings file, skipping check
```

#### Warning Signs
```
❌ Missing required environment variables
❌ Cannot access repository
❌ Database connection failed
❌ Database health check failed
⚠️  No accessible channels found
⚠️  Migration mode not supported
OSError: [Errno 16] Device or resource busy
```

### Emergency Recovery

#### Reset Everything
```bash
# Stop service
sudo systemctl stop chatd-internships

# Clean Docker
docker stop chatd-bot 2>/dev/null || true
docker rm chatd-bot 2>/dev/null || true

# Reset data
sudo rm -rf /var/lib/chatd/data/*
sudo ./scripts/sync-repo-data.sh

# Restart
sudo systemctl start chatd-internships
```

## File Structure Reference

After successful setup, your system should have:

```
/etc/chatd/
├── .env                          # Bot configuration
└── .env.postgres                 # PostgreSQL password (if using database)

/var/lib/chatd/
├── data/
│   ├── previous_data.json        # Baseline job listings (JSON mode)
│   ├── message_tracking.json     # Sent messages tracking (JSON mode)
│   └── current_head.txt          # Git commit tracking
├── repo/                         # GitHub repository contents
│   ├── .git/
│   ├── .github/
│   │   └── scripts/
│   │       └── listings.json     # Current job listings
│   └── README.md
└── logs/                         # Application logs

/usr/local/bin/
├── chatd                         # Main management command
├── chatd-logs                    # Log viewer
└── chatd-loglevel               # Dynamic log control

/etc/systemd/system/
└── chatd-internships.service     # System service

# Docker Components (if using PostgreSQL)
Docker Containers:
├── chatd-bot                     # Main bot container
└── chatd-postgres               # PostgreSQL database container

Docker Volumes:
└── postgres_data                 # Persistent database storage
```

## Security Considerations

1. **File Permissions**: Configuration file contains sensitive Discord token
   ```bash
   sudo chmod 600 /etc/chatd/.env
   ```

2. **Firewall**: No inbound ports needed (bot connects outbound only)

3. **Updates**: Keep system and Docker updated regularly
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

4. **Monitoring**: Regularly check logs for unusual activity

## Performance Notes

- **Memory Usage**: ~50-100MB RAM typical
- **Disk Usage**: ~200MB for Docker image + data
- **CPU Usage**: Minimal (periodic git pulls and Discord API calls)
- **Network**: Outbound HTTPS only (GitHub, Discord APIs)

## Next Steps

After successful setup:

1. **Monitor Initial Operation**: Watch logs for 24 hours to ensure stability
2. **Set Up Backups**: Consider backing up `/var/lib/chatd/data/` periodically
3. **Configure Alerts**: Set up monitoring for service failures if desired
4. **Update Procedures**: Bookmark this guide for future updates

The bot is now ready for production use! 🚀