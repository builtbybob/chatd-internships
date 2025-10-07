# Ch@d Internships Bot - Complete Setup Guide

This guide covers the complete setup process for the ChatD Internships Discord bot using the automated setup script. The bot can be deployed for production use (`chatd`) or as additional isolated environments for development, testing, or specialized purposes.

## Overview

The ChatD Internships bot monitors internship repositories (like [Summer2026-Internships](https://github.com/SimplifyJobs/Summer2026-Internships)) for new job postings and posts updates to Discord channels. The system uses:

- **Automated setup script** for one-command installation
- **Docker Compose** for containerized deployment
- **PostgreSQL** database for job posting and message tracking data
- **systemd** for automatic startup and service management
- **Management scripts** for easy administration
- **Multi-environment support** for isolated deployments

## Quick Start - Automated Installation

### Prerequisites

Before starting, ensure you have:

- **Linux system** (tested on Ubuntu/Debian/Raspberry Pi OS)
- **Docker and Docker Compose** installed
- **Git** installed
- **Discord bot token** and **channel IDs**
- **Root/sudo access** for system configuration

### System Preparation

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

### Get ChatD Repository

```bash
# Clone the ChatD repository
cd ~
git clone https://github.com/builtbybob/chatd-internships.git
cd chatd-internships
```

### Discord Bot Setup

**Before running the setup script**, create your Discord bot:

1. **Create New Application**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" 
   - Name it appropriately (e.g., "ChatD Production" or "ChatD Development")

2. **Configure Bot**:
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the bot token (you'll need this for setup)
   - Enable necessary intents if required

3. **Add to Discord Server**:
   - Go to "OAuth2" → "URL Generator"
   - Select "bot" scope
   - Select necessary permissions (Send Messages, Add Reactions, etc.)
   - Use generated URL to add bot to your Discord server

4. **Get Channel IDs**:
   - In Discord, enable Developer Mode (User Settings → Advanced → Developer Mode)
   - Right-click on channels where you want job postings → Copy ID

### Automated Setup

The setup script handles everything automatically:

```bash
# Run the automated setup script
sudo ./scripts/setup-chatd-environment.sh <environment-name>
```

**Environment naming examples:**
- `chatd` (production)
- `chatd-dev` (development)
- `chatd-internships` (internships focus)
- `chatd-newgrad` (new grad focus)
- `chatd-fall2025` (seasonal)

The script will prompt you for:

- **Discord Bot Token** (from Discord Developer Portal)
- **Channel IDs** (comma-separated list from Discord)
- **Repository URL** (defaults to SimplifyJobs Summer2026-Internships)
- **Database Password** (auto-generated if not provided)

**What the script does automatically:**

✅ **Clones the specified repository**  
✅ **Builds Docker images** (eliminates startup delays)  
✅ **Generates secure database passwords**  
✅ **Creates isolated Docker containers and networks**  
✅ **Configures environment variables**  
✅ **Sets up robust systemd service** with proper health checks  
✅ **Optionally migrates existing data** from listings.json to database  
✅ **Creates management commands** for easy administration  
✅ **Sets proper file permissions** and ownership  
✅ **Validates configuration** before completion  

### Start Your Environment

After setup completes:

```bash
# Start the environment (replace <environment-name> with your chosen name)
<environment-name> start

# Enable auto-start on boot
<environment-name> enable

# Check status
<environment-name> status

# View logs
<environment-name> logs -f
```

**Example for a `chatd` environment:**
```bash
chatd start
chatd enable  
chatd status
chatd logs -f
```

## Environment Management

### Naming Convention

Each environment gets its own isolated setup:

- **Environment name**: Used for all components (e.g., `chatd`, `chatd-dev`)
- **Directory**: `/opt/<env-name>/`
- **Containers**: `<env-name>-postgres`, `<env-name>-bot`
- **Database**: `<env_name_underscores>` (e.g., `chatd_dev`)
- **Network**: `<env-name>-network`
- **Volumes**: `<env-name>_postgres_data`, etc.
- **Service**: `<env-name>.service`
- **Command**: `/usr/local/bin/<env-name>`

### Management Commands

Each environment gets its own management command:

```bash
# Environment status and control
<environment-name> status          # Check status
<environment-name> start           # Start services
<environment-name> stop            # Stop services  
<environment-name> restart         # Restart services
<environment-name> enable          # Enable auto-start on boot
<environment-name> disable         # Disable auto-start

# Logs and monitoring
<environment-name> logs            # View all logs
<environment-name> logs -f         # Follow logs in real-time
<environment-name> logs bot        # Bot logs only
<environment-name> logs postgres   # Database logs only

# Container access
<environment-name> shell           # Bot container shell
<environment-name> shell postgres  # Database container shell
<environment-name> db              # PostgreSQL command line

# Maintenance
<environment-name> build           # Build containers
<environment-name> update          # Pull, build, restart
<environment-name> cleanup         # Clean up Docker resources
```

### Multiple Environment Examples

```bash
# Production environment
sudo ./scripts/setup-chatd-environment.sh chatd
chatd start && chatd enable

# Development environment  
sudo ./scripts/setup-chatd-environment.sh chatd-dev
chatd-dev start

# Specialized environments
sudo ./scripts/setup-chatd-environment.sh chatd-internships
sudo ./scripts/setup-chatd-environment.sh chatd-newgrad
sudo ./scripts/setup-chatd-environment.sh chatd-fall2025

# Each runs independently with its own:
# - Discord bot
# - Database
# - Configuration  
# - Ports
# - Management commands
```

## Advanced Features

### Automatic Features

The setup script provides several automatic capabilities:

- **Port Assignment**: Automatically assigned unique ports (PostgreSQL: 5433+, Web: 8081+)
- **Container Isolation**: Separate networks and volumes per environment
- **Performance Optimization**: Includes optimized message posting delays
- **Database Migration**: Optional automation to migrate existing listings.json data
- **Build Optimization**: Docker images built during setup for fast startup
- **Health Verification**: Service doesn't complete until containers are verified working

### Database Migration Support

During setup, the script can automatically migrate existing data:

```
📊 Database Migration
The system can automatically migrate data from listings.json to the database.
Would you like to migrate existing data to the database? (y/n): y
```

**What happens during migration:**
- Creates Python virtual environment for migration dependencies
- Starts environment temporarily for data import
- Runs migration script with progress tracking
- Validates data integrity
- Cleans up and continues with normal setup

### Reliability Improvements

The setup script incorporates production-tested reliability features:

- **Python-based health checks**: Replaces failing `pgrep` commands with reliable file existence checks
- **Oneshot systemd configuration**: Prevents restart loops and service conflicts
- **Pre-built Docker images**: Eliminates startup delays and build failures during deployment
- **Proper container lifecycle**: Start, stop, and reload work correctly with Docker and systemd integration

## Verification and Monitoring

### Successful Operation Verification

After setup, verify your environment is working correctly:

```bash
# Check service status
<environment-name> status

# Should show:
# ● <environment-name>.service - ChatD Internships Bot (<environment-name>)
#    Loaded: loaded
#    Active: active (exited) since <timestamp>

# Check containers are running
docker ps | grep <environment-name>

# Should show both containers:
# <environment-name>-postgres    # Database
# <environment-name>-bot         # Bot application

# Monitor startup logs
<environment-name> logs -f

# Look for successful startup sequence:
# ✅ Logging configured with level: INFO
# ✅ Configuration validation completed successfully  
# ✅ Database connection successful (PostgreSQL)
# ✅ Discord connection successful (logged in as YourBot#1234)
# ✅ Can access X/X configured channels
# 🔍 No updates to listings file, skipping check
```

The message "No updates to listings file, skipping check" confirms that message replay prevention worked correctly.

### Service Management

```bash
# Basic service control
<environment-name> start          # Start services
<environment-name> stop           # Stop services
<environment-name> restart        # Restart services
<environment-name> status         # Check status

# Auto-start management
<environment-name> enable         # Enable auto-start on boot
<environment-name> disable        # Disable auto-start

# Alternative systemctl commands
sudo systemctl start <environment-name>
sudo systemctl stop <environment-name>
sudo systemctl restart <environment-name>
sudo systemctl status <environment-name>
```

### Log Management

```bash
# View logs
<environment-name> logs           # Recent logs
<environment-name> logs -f        # Follow logs in real-time
<environment-name> logs -n 100    # Last 100 lines

# Component-specific logs
<environment-name> logs bot       # Bot logs only
<environment-name> logs postgres  # Database logs only

# System service logs
sudo journalctl -u <environment-name> -f
```

### Database Management

```bash
# Connect to database
<environment-name> db

# Or using docker directly
docker exec -it <environment-name>-postgres psql -U chatd -d <env_name_underscores>

# Common database queries:
# \dt                                    # List tables
# \dv                                    # List views  
# SELECT COUNT(*) FROM job_postings;     # Count job postings
# SELECT COUNT(*) FROM message_tracking; # Count tracked messages
# \q                                     # Quit psql

# Database backup
docker exec <environment-name>-postgres pg_dump -U chatd <env_name_underscores> > /opt/<environment-name>/data/backup_$(date +%Y%m%d_%H%M%S).sql
```

## Updates and Maintenance

### Updating Environments

```bash
# Update to latest code and redeploy
<environment-name> update

# Build new Docker images
<environment-name> build

# Manual update process (if needed)
cd /opt/<environment-name>
sudo git pull
<environment-name> build
<environment-name> restart
```

### Repository Synchronization

```bash
# Sync to latest repository version
cd /opt/<environment-name>
sudo ./scripts/sync-repo-data.sh

# Sync to specific commit (useful for testing)
sudo ./scripts/sync-repo-data.sh abc123def456
```

## Troubleshooting

### Quick Diagnosis

```bash
# Check environment status
<environment-name> status

# Check containers
docker ps | grep <environment-name>

# Check recent logs
<environment-name> logs --tail=50

# Test database connectivity
<environment-name> db -c "SELECT 1;"
```

### Common Issues and Solutions

#### 1. Service Won't Start

```bash
# Check systemd service status
sudo systemctl status <environment-name>

# Check container logs
<environment-name> logs

# Common fixes:
sudo systemctl daemon-reload
<environment-name> restart

# If containers aren't running:
cd /opt/<environment-name>
docker-compose up -d
```

#### 2. Database Connection Issues

```bash
# Verify PostgreSQL container is running
docker ps | grep <environment-name>-postgres

# Check database connectivity
docker exec <environment-name>-postgres pg_isready -U chatd

# View database logs
<environment-name> logs postgres

# Restart database if needed
docker restart <environment-name>-postgres
```

#### 3. Discord Connection Issues

```bash
# Verify Discord token in configuration
sudo grep DISCORD_TOKEN /opt/<environment-name>/.env

# Check channel IDs format
sudo grep CHANNEL_IDS /opt/<environment-name>/.env

# Test with debug logging temporarily
# Edit /opt/<environment-name>/.env and change LOG_LEVEL=DEBUG
<environment-name> restart
<environment-name> logs -f
```

#### 4. Permission Errors

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 /opt/<environment-name>/data
sudo chown -R 1000:1000 /opt/<environment-name>/logs
sudo chown -R 1000:1000 /opt/<environment-name>/Summer2026-Internships

# Fix configuration permissions
sudo chmod 600 /opt/<environment-name>/.env
```

#### 5. Port Conflicts

```bash
# Check what ports are in use
ss -tuln | grep 5432
ss -tuln | grep 8080

# The setup script automatically assigns unique ports, but if conflicts occur:
# Edit /opt/<environment-name>/docker-compose.yml and change port mappings
```

#### 6. Health Check Issues

The setup script uses reliable Python-based health checks. If issues persist:

```bash
# Test health check manually
docker exec <environment-name>-bot python3 -c "import os; exit(0 if os.path.exists('/app/main.py') else 1)"
echo $?  # Should be 0

# Check health status
docker inspect <environment-name>-bot | grep -A 10 Health
```

### Systemd Service Issues

```bash
# Check service status in detail
sudo systemctl status <environment-name> -l

# View service logs
sudo journalctl -u <environment-name> --no-pager

# Test start/stop cycle
sudo systemctl stop <environment-name>
docker ps | grep <environment-name>  # Should show no containers
sudo systemctl start <environment-name>
docker ps | grep <environment-name>  # Should show running containers
```

### Emergency Recovery

```bash
# Complete environment reset (nuclear option)
<environment-name> stop
cd /opt/<environment-name>
docker-compose down -v
docker system prune -f
sudo rm -rf data/*
sudo ./scripts/sync-repo-data.sh
<environment-name> start
```

### Log Analysis

#### Successful Startup Sequence

```
[INFO] 🚀 Starting ChatD Internships Bot...
[INFO] 🔧 Validating configuration...
[INFO] ✅ Configuration validation passed.
[INFO] ✅ Configuration validation completed successfully
[INFO] 🤖 Starting Discord bot...
[INFO] Database connection successful (PostgreSQL)
[INFO] Starting bot with environment configuration...
[INFO] logging in using static token
[INFO] Logged in as YourBot#1234
[INFO] Bot is ready and monitoring X channels
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

## Resource Usage and Planning

### Per Environment Resource Requirements

- **Memory Usage**: ~100-200MB total (bot: ~50-100MB, PostgreSQL: ~50-100MB)
- **Disk Usage**: ~500MB-1GB per environment (containers + data)
- **CPU Usage**: Minimal (periodic git pulls and Discord API calls)
- **Network**: Outbound HTTPS only (GitHub API, Discord API)

### Multiple Environment Capacity

With typical server resources:

- **Small VPS (2GB RAM)**: 3-5 environments comfortably
- **Medium VPS (4GB RAM)**: 8-12 environments  
- **Large VPS (8GB+ RAM)**: 15+ environments
- **Disk space**: ~69GB can support 20+ environments easily

### Port Assignment

The setup script automatically manages ports:

- **PostgreSQL**: 5433, 5434, 5435, etc. (production uses internal networking)
- **Web interfaces**: 8081, 8082, 8083, etc. (if enabled)
- **Health checks**: Automatic port conflict detection and resolution

## Security and Best Practices

### Automated Security Configuration

The setup script automatically:

- **Secures environment files** (600 permissions)
- **Isolates networks** (no cross-environment communication)
- **Generates secure passwords** (database access)
- **Sets proper ownership** (Docker user permissions)

### Additional Security Recommendations

1. **Keep System Updated**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Regular Backups**
   ```bash
   # Automated backup setup
   sudo crontab -e
   # Add: 0 2 * * * docker exec <env>-postgres pg_dump -U chatd <env_db> > /opt/<env>/data/backup_$(date +\%Y\%m\%d).sql
   ```

3. **Monitor Resources**
   ```bash
   # Check Docker resource usage
   docker stats
   
   # Monitor disk usage
   df -h
   docker system df
   ```

4. **Environment Isolation**
   - Each environment has its own Discord bot token
   - Separate databases prevent data mixing
   - Independent networks prevent container communication

## Production Deployment Best Practices

### Recommended Production Setup

```bash
# Production environment with stable naming
sudo ./scripts/setup-chatd-environment.sh chatd
chatd enable  # Auto-start on boot
chatd start

# Development environment for testing
sudo ./scripts/setup-chatd-environment.sh chatd-dev
# (don't enable auto-start for dev environments)

# Specialized environments as needed
sudo ./scripts/setup-chatd-environment.sh chatd-internships
sudo ./scripts/setup-chatd-environment.sh chatd-newgrad
```

### Monitoring and Alerting

```bash
# Basic monitoring commands
<env-name> status           # Service status
<env-name> logs --tail=20   # Recent logs
docker stats                # Resource usage

# Log file locations for external monitoring
/opt/<env-name>/logs/
journalctl -u <env-name>
docker logs <env-name>-bot
```

### Update Procedures

```bash
# Regular update schedule (weekly/monthly)
<env-name> update    # Pulls latest code and rebuilds

# Emergency updates
cd /opt/<env-name>
git pull
<env-name> build
<env-name> restart
```

## File Structure Reference

After successful setup, each environment has the following structure:

```
/opt/<environment-name>/                 # Environment working directory
├── .env                                 # Environment configuration
├── docker-compose.yml                  # Container orchestration
├── <environment-name>.service           # Systemd service definition  
├── Dockerfile                          # Bot container build
├── requirements.txt                    # Python dependencies
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
│   ├── setup-chatd-environment.sh     # Setup script (for additional envs)
│   ├── sync-repo-data.sh              # Repository sync utility
│   └── migrate_json_to_database.py    # Migration script
├── data/                               # Application data
│   ├── previous_data.json              # Baseline job listings
│   ├── message_tracking.json           # Message tracking (JSON fallback)
│   └── current_head.txt               # Git commit tracking
├── logs/                               # Application logs
│   └── chatd.log                      # Main log file
└── Summer2026-Internships/             # Monitored repository (or custom)
    ├── .git/
    ├── .github/
    │   └── scripts/
    │       └── listings.json           # Current job listings
    └── README.md

# Docker Components per Environment
Docker Containers:
├── <env-name>-bot                      # Main bot container
└── <env-name>-postgres                 # PostgreSQL database

Docker Volumes:
├── <env-name>_postgres_data            # Persistent database storage
└── <env-name>_<additional-volumes>     # Other environment-specific volumes

Docker Networks:
└── <env-name>-network                  # Isolated network per environment

# System Integration
/etc/systemd/system/
└── <environment-name>.service          # Systemd service

/usr/local/bin/
└── <environment-name>                  # Management command for this environment
```

**Example for `chatd` environment:**
- Directory: `/opt/chatd/`
- Containers: `chatd-bot`, `chatd-postgres`  
- Service: `chatd.service`
- Command: `/usr/local/bin/chatd`
- Database: `chatd`
- Network: `chatd-network`

**Example for `chatd-dev` environment:**
- Directory: `/opt/chatd-dev/`
- Containers: `chatd-dev-bot`, `chatd-dev-postgres`
- Service: `chatd-dev.service`  
- Command: `/usr/local/bin/chatd-dev`
- Database: `chatd_dev`
- Network: `chatd-dev-network`

## Use Cases and Examples

### Development Workflow

```bash
# Set up production environment
sudo ./scripts/setup-chatd-environment.sh chatd
chatd enable && chatd start

# Set up development environment for testing
sudo ./scripts/setup-chatd-environment.sh chatd-dev
chatd-dev start

# Test changes in development
# Edit code, then:
chatd-dev build
chatd-dev restart
chatd-dev logs -f

# Deploy to production when ready
chatd update
```

### Multi-Purpose Deployment

```bash
# Internship tracking (main)
sudo ./scripts/setup-chatd-environment.sh chatd-internships

# New grad role tracking
sudo ./scripts/setup-chatd-environment.sh chatd-newgrad

# Seasonal tracking
sudo ./scripts/setup-chatd-environment.sh chatd-fall2025

# Each monitors different repositories and posts to different Discord channels
```

### Testing and Staging

```bash
# Production
sudo ./scripts/setup-chatd-environment.sh chatd-prod
chatd-prod enable

# Staging for testing updates
sudo ./scripts/setup-chatd-environment.sh chatd-staging

# Development for active coding
sudo ./scripts/setup-chatd-environment.sh chatd-dev

# Each can run different branches or configurations
```

## Next Steps

After successful setup:

1. **Monitor Initial Operation**: Watch logs for 24 hours to ensure stability
   ```bash
   <environment-name> logs -f
   ```

2. **Set Up Monitoring**: Consider setting up alerts for service failures
   ```bash
   # Add to crontab for basic monitoring
   */5 * * * * /usr/local/bin/<environment-name> status > /dev/null || echo "Environment <environment-name> is down!" | mail -s "ChatD Alert" admin@example.com
   ```

3. **Configure Backups**: Set up regular backups of database and configuration
   ```bash
   # Daily database backup
   0 2 * * * docker exec <environment-name>-postgres pg_dump -U chatd <env_database> > /opt/<environment-name>/data/backup_$(date +\%Y\%m\%d).sql
   ```

4. **Performance Tuning**: Monitor resource usage and adjust as needed
   ```bash
   docker stats
   <environment-name> logs | grep "performance\|slow\|timeout"
   ```

5. **Additional Environments**: Create more environments as needed
   ```bash
   sudo ./scripts/setup-chatd-environment.sh <new-environment-name>
   ```

## Conclusion

The ChatD Internships bot is now ready for production use! 🚀

**Key Benefits of the Automated Setup:**
- ✅ **One-command installation** - no manual configuration
- ✅ **Multi-environment support** - isolate development, staging, production
- ✅ **Automatic reliability features** - health checks, restart policies, proper systemd integration
- ✅ **Built-in management commands** - easy operation and monitoring
- ✅ **Production-tested configuration** - incorporates lessons learned from debugging
- ✅ **Optional data migration** - seamless upgrade from JSON to database storage

The setup script can be used for both first-time installations and creating additional environments, making it the recommended approach for all ChatD deployments.

For support, issues, or contributions, visit: https://github.com/builtbybob/chatd-internships

---

## Alternative Installation Methods

### Manual Installation (Advanced Users)

For users who prefer manual setup or need custom configurations, refer to the legacy manual installation process. However, the automated setup script is recommended for all standard deployments as it:

- Incorporates production-tested reliability improvements
- Handles all edge cases and error conditions
- Provides consistent, repeatable deployments
- Includes automatic health checks and systemd integration
- Supports both first installations and additional environments

### Custom Repository Setup

The setup script supports custom repositories:

```bash
# During setup, when prompted for repository URL:
Repository URL (default: https://github.com/SimplifyJobs/Summer2026-Internships.git): https://github.com/your-org/your-internship-repo.git
```

This allows monitoring of:
- Private internship repositories
- Forked repositories with custom modifications  
- Alternative job posting repositories
- Multiple repositories per environment

### Advanced Configuration

After setup, you can customize environment settings:

```bash
# Edit environment configuration
sudo nano /opt/<environment-name>/.env

# Restart to apply changes
<environment-name> restart
```

**Common customizations:**
- `CHECK_INTERVAL_MINUTES`: How often to check for updates
- `MAX_POST_AGE_DAYS`: Maximum age of posts to include
- `ENABLE_REACTIONS`: Enable/disable reaction features
- `LOG_LEVEL`: Adjust logging verbosity