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