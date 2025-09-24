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
sudo apt install -y git docker.io curl vim

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

## Step 3: Discord Bot Configuration

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

**How to get Discord Channel ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click on the channel → Copy ID

## Step 4: Repository Data Setup

### Initial Repository Clone

```bash
# Clone the internships repository to the correct location
cd /var/lib/chatd/repo/
sudo git clone https://github.com/SimplifyJobs/Summer2026-Internships.git temp_clone

# Move contents to the correct structure (avoid nested directories)
sudo mv temp_clone/* .
sudo mv temp_clone/.* . 2>/dev/null || true
sudo rmdir temp_clone

# Set correct ownership
sudo chown -R 1000:1000 /var/lib/chatd/repo/
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

## Step 5: Install Management Scripts

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

## Step 6: Build and Deploy

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

## Step 7: Management and Monitoring

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

#### 4. Bot Replays Old Messages
```bash
# Stop service and re-sync data
sudo systemctl stop chatd-internships
sudo ./scripts/sync-repo-data.sh
sudo systemctl start chatd-internships
```

#### 5. Docker Issues
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
⚠️  No accessible channels found
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
└── .env                          # Bot configuration

/var/lib/chatd/
├── data/
│   ├── previous_data.json        # Baseline job listings
│   ├── message_tracking.json     # Sent messages tracking
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