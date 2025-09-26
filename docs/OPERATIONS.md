# ChatD Internships Bot - Operations Guide

This guide covers operating, managing, and troubleshooting the ChatD Internships Discord bot in production using Docker and systemd.

## 🚀 Initial Setup

**For initial installation and configuration, see:**

👉 [SETUP.md - Initial Setup Guide](./SETUP.md)

---

## 🛠️ Management Commands

After running the setup script, you'll have these management commands available:

### Main Control (chatd)
- `chatd start`         - Start the bot service
- `chatd stop`          - Stop the bot service
- `chatd restart`       - Restart the bot service
- `chatd status`        - Show service status
- `chatd enable`        - Enable auto-start on boot
- `chatd disable`       - Disable auto-start
- `chatd logs`          - Show recent logs (alias for chatd-logs)
- `chatd data`          - Show data status (alias for chatd-data)
- `chatd backup`        - Create backup (alias for chatd-backup)
- `chatd build`         - Build Docker image (alias for chatd-build)
- `chatd deploy`        - Deploy with existing image (alias for chatd-deploy)
- `chatd update`        - Build and deploy together (alias for chatd-update)
- `chatd version`       - Show version information (alias for chatd-version)
- `chatd cleanup`       - Manual image cleanup (alias for chatd-cleanup)
- `chatd images`        - List all ChatD images (alias for chatd-images)
- `chatd prune`         - Aggressive cleanup (alias for chatd-prune)
- `chatd disk`          - Show disk usage and image status (alias for chatd-disk)

### Monitoring & Debugging
- `chatd logs`          - Show recent logs
- `chatd logs -f`       - Follow logs in real-time
- `chatd logs --docker` - Show Docker container logs
- `chatd logs --system` - Show systemd service logs
- `chatd data`          - Show data status and statistics
- `chatd disk`          - Show disk usage, free space, and image status

### Maintenance & Image Management
- `chatd build [BRANCH]`    - Build Docker image with smart detection
- `chatd deploy`            - Deploy with existing image
- `chatd update [BRANCH]`   - Build and deploy together
- `chatd cleanup [--count N|--dry-run]` - Manual Docker image cleanup (retention policy)
- `chatd prune`             - Aggressive cleanup (keep only latest image)
- `chatd images`            - List all ChatD images with sizes
- `chatd version`           - Show current version, list images, clean old images

### Backup & Data Inspection
- `chatd backup`            - Create backup of bot data and config
- `chatd data`              - Inspect bot data files, repo status, container status, service status, recent logs, disk usage

### Log Level Control
- `chatd-loglevel <level>`  - Change log level without restarting the bot (levels: debug, info, warning, error, critical)

### Advanced Log Options
```bash
chatd-logs -n 100        # Show last 100 lines
chatd-logs -f            # Follow logs
chatd-logs --docker -f   # Follow Docker logs
chatd-logs --system      # Show systemd logs
```

### Disk Usage & Monitoring
- `chatd disk`              - Show disk usage, free/total space, image count, and status
    - Alerts if disk usage >80% or >90%
    - Prometheus-style metrics: `chatd disk --metrics`

### Docker Image Cleanup
- `chatd cleanup`           - Manual cleanup, retention policy via `CHATD_DOCKER_RETENTION` env var
- `chatd prune`             - Aggressive prune, keep only latest image

### Version Management
- `chatd version`           - Show current version, list images, clean old images

### Environment Variables
- `CHATD_BRANCH`            - Default branch for build/update commands
- `CHATD_DOCKER_RETENTION`  - Number of images to retain (default: 3)


## 🔄 Updates and Maintenance


### Update Bot Code
```bash
# Recommended: Build and deploy with retention and disk checks
chatd update

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
You can control log level dynamically with `chatd-loglevel <level>`.

## 🔧 Troubleshooting


### Check Service Status
```bash
chatd status
```

### View Recent Logs
```bash
chatd logs -n 50
```

### Disk Usage & Image Status
```bash
chatd disk
chatd disk --metrics   # Show Prometheus-style metrics
```

### Manual Docker Image Cleanup
```bash
chatd cleanup --dry-run   # Preview images to be deleted
chatd cleanup --count 5   # Keep 5 images
chatd prune               # Keep only latest image
chatd images              # List images with sizes
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

**Disk space issues / image accumulation:**
- Run `chatd disk` to check usage and image count
- Use `chatd cleanup` or `chatd prune` to remove old images
- Set `CHATD_DOCKER_RETENTION` in `.env` to control retention

## 🔒 Security Considerations

- Configuration file (`/etc/chatd/.env`) has 600 permissions (root only)
- Bot runs as non-root user (UID 1000) inside container
- Data directories have proper ownership (1000:1000)
- Docker container runs with `--restart unless-stopped` for resilience
- Logs are automatically rotated to prevent disk space issues

## 📊 Monitoring


### Service Health & Disk Monitoring
```bash
# Service status
chatd status

# Resource usage
docker stats chatd-bot

# Data usage
chatd data

# Disk usage and image status
chatd disk
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
1. Check this operations guide
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
chatd build              # Build new image
chatd update             # Build and deploy with retention/disk checks
chatd backup             # Create backup
chatd disk               # Show disk usage and image status
chatd cleanup            # Manual image cleanup
chatd prune              # Aggressive prune (keep only latest)
chatd images             # List images with sizes
chatd-loglevel <level>   # Change log level without restart

# Files and directories
/etc/chatd/.env                      # Configuration
/var/lib/chatd/                      # Data directory
/etc/systemd/system/chatd-internships.service  # Service file
/usr/local/bin/chatd*                # Management scripts
``
