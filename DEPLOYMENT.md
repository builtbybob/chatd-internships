# ChatD Internships Bot - Deployment Guide

This guide covers deploying the ChatD Internships Discord bot using Docker and systemd for production use.

## 🚀 Quick Start

```bash
# 1. Set up configuration
sudo mkdir -p /etc/chatd
sudo cp .env.example /etc/chatd/.env
sudo nano /etc/chatd/.env  # Edit with your settings

# 2. Install systemd service
sudo cp chatd-internships.service /etc/systemd/system/
sudo systemctl daemon-reload

# 3. Create management scripts
sudo bash scripts/create-management-scripts.sh

# 4. Start the bot
sudo systemctl enable chatd-internships
sudo systemctl start chatd-internships

# 5. Check status
chatd status
```

## 📋 Prerequisites

- **Docker**: Container runtime
- **systemd**: Service management
- **Git**: For code updates
- **Linux system**: Ubuntu/Debian recommended

Install Docker if not present:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER  # Optional: run Docker without sudo
```

## ⚙️ Configuration Setup

### 1. Create Configuration Directory

```bash
sudo mkdir -p /etc/chatd
sudo chmod 750 /etc/chatd
```

### 2. Create Environment File

```bash
sudo tee /etc/chatd/.env << EOF
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here
CHANNEL_IDS=123456789,987654321

# Logging Configuration
LOG_LEVEL=INFO

# Bot Behavior
ENABLE_REACTIONS=false
MAX_RETRIES=3
CHECK_INTERVAL_MINUTES=1

# Repository Settings (usually don't need to change these)
REPO_URL=https://github.com/SimplifyJobs/Summer2026-Internships.git
EOF
```

### 3. Secure Configuration

```bash
sudo chmod 600 /etc/chatd/.env
sudo chown root:root /etc/chatd/.env
```

## 🐳 Docker Deployment

### Service Installation

```bash
# Copy service file
sudo cp chatd-internships.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable chatd-internships
```

### Directory Structure

The deployment creates the following structure:

```
/var/lib/chatd/
├── data/                 # Bot persistent data
│   ├── previous_data.json
│   ├── message_tracking.json
│   └── current_head.txt
├── repo/                 # Git repository clone
│   └── Summer2026-Internships/
└── logs/                 # Application logs
    └── chatd.log

/etc/chatd/
└── .env                  # Configuration (secure)
```

## 🛠️ Management Commands

After running the setup script, you'll have these commands available:

### Main Control
- `chatd start` - Start the bot
- `chatd stop` - Stop the bot  
- `chatd restart` - Restart the bot
- `chatd status` - Check service status
- `chatd enable` - Enable auto-start on boot
- `chatd disable` - Disable auto-start

### Monitoring & Debugging
- `chatd logs` - Show recent logs
- `chatd logs -f` - Follow logs in real-time
- `chatd logs --docker` - Show Docker container logs
- `chatd logs --system` - Show systemd service logs
- `chatd data` - Show data status and statistics

### Maintenance
- `chatd build` - Update code and rebuild
- `chatd backup` - Create backup of bot data

### Advanced Log Options
```bash
chatd-logs -n 100        # Show last 100 lines
chatd-logs -f            # Follow logs
chatd-logs --docker -f   # Follow Docker logs
chatd-logs --system      # Show systemd logs
```

## 🔄 Updates and Maintenance

### Update Bot Code

```bash
# Automatic update (recommended)
chatd build

# Manual update
cd /home/apathy/dev/chatd-internships
git pull
docker build -t chatd-internships:latest .
chatd restart
```

### Backup and Restore

```bash
# Create backup
chatd backup

# Restore backup (replace TIMESTAMP with actual timestamp)
sudo tar -xzf /tmp/chatd_backup_TIMESTAMP.tar.gz -C /
```

### Log Management

Logs are automatically rotated by Docker (10MB max, 3 files). Application logs are in `/var/lib/chatd/logs/chatd.log`.

## 🔧 Troubleshooting

### Check Service Status
```bash
chatd status
```

### View Recent Logs
```bash
chatd logs -n 50
```

### Debug Container Issues
```bash
# Check if container is running
docker ps | grep chatd-bot

# View Docker logs
chatd logs --docker

# Execute commands in container
docker exec -it chatd-bot /bin/bash
```

### Common Issues

**Service won't start:**
- Check configuration: `sudo nano /etc/chatd/.env`
- Verify Docker is running: `sudo systemctl status docker`
- Check systemd logs: `chatd logs --system`

**Bot can't connect to Discord:**
- Verify Discord token in `/etc/chatd/.env`
- Check channel IDs are correct
- Ensure bot has proper permissions in Discord

**Repository clone fails:**
- Check internet connectivity
- Verify `/var/lib/chatd` permissions
- Check Docker container logs: `chatd logs --docker`

**No data persistence:**
- Check volume mounts: `docker inspect chatd-bot`
- Verify directory permissions: `ls -la /var/lib/chatd/`
- Check if data directory exists and is writable

## 🔒 Security Considerations

- Configuration file (`/etc/chatd/.env`) has 600 permissions (root only)
- Bot runs as non-root user (UID 1000) inside container
- Data directories have proper ownership (1000:1000)
- Docker container runs with `--restart unless-stopped` for resilience
- Logs are automatically rotated to prevent disk space issues

## 📊 Monitoring

### Service Health
```bash
# Service status
chatd status

# Resource usage
docker stats chatd-bot

# Data usage
chatd data
```

### Automated Monitoring Setup

For production, consider setting up monitoring:

```bash
# Add to crontab for health checks
# Check every 5 minutes, restart if down
*/5 * * * * /usr/bin/systemctl is-active --quiet chatd-internships || /usr/bin/systemctl start chatd-internships
```

## 🆘 Support

For issues:
1. Check this deployment guide
2. Review logs: `chatd logs -f`
3. Check service status: `chatd status`  
4. Verify configuration: `sudo cat /etc/chatd/.env`
5. Test Docker manually: `docker run -it --rm chatd-internships:latest python -c "import chatd.config; print('OK')"`

---

## 📝 Quick Reference

```bash
# Essential commands
chatd start              # Start bot
chatd stop               # Stop bot
chatd status             # Check status
chatd logs -f            # Follow logs
chatd build              # Update & rebuild
chatd backup             # Create backup

# Files and directories
/etc/chatd/.env                      # Configuration
/var/lib/chatd/                      # Data directory
/etc/systemd/system/chatd-internships.service  # Service file
/usr/local/bin/chatd*                # Management scripts
```
