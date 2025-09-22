# ChatD Migration Quick Guide

## 🚀 One-Command Migration

### Step 1: Backup Current System
```bash
cd ~/dev/chatd-internships
./scripts/backup-system.sh
```

This creates a complete backup including:
- ✅ ChatD configuration (`/etc/chatd/.env`)
- ✅ Application data (`/var/lib/chatd/`)
- ✅ SSH keys (`~/.ssh/`)
- ✅ Docker images (ChatD containers)
- ✅ System information
- ✅ Automated restore script

### Step 2: Transfer to New System
```bash
# The backup will be in /tmp/chatd-migration-backup/
# Copy the .tar.gz file to your new Raspberry Pi

# Example transfer methods:
scp /tmp/chatd-migration-backup/chatd_backup_*.tar.gz user@new-pi:~/
# OR copy to USB drive, cloud storage, etc.
```

### Step 3: Restore on New System
```bash
# On the new Raspberry Pi:
tar xzf chatd_backup_*.tar.gz
cd chatd_backup_*/
./install-on-new-system.sh
```

### Step 4: Verify Installation
```bash
cd ~/dev/chatd-internships
./scripts/verify-system.sh
```

## 📋 Migration Checklist

**Before Migration:**
- [ ] Run backup script on current system
- [ ] Verify backup completed successfully
- [ ] Copy backup file to new system

**After Migration:**
- [ ] Fresh Raspberry Pi OS installed on larger SD card
- [ ] Docker installed: `sudo apt install docker.io`
- [ ] User added to docker group: `sudo usermod -aG docker $USER`
- [ ] Restore script completed without errors
- [ ] Verification script shows all green checks
- [ ] ChatD service running: `sudo chatd status`

## 🔧 Quick Commands

```bash
# Check system health
./scripts/verify-system.sh

# View service status
sudo chatd status

# Follow logs
sudo chatd-logs -f

# Test dynamic logging
sudo chatd-loglevel debug
sudo chatd-loglevel info

# Restart if needed
sudo systemctl restart chatd-internships
```

## ⚠️ Troubleshooting

If something goes wrong:

1. **Check the verification script output** - it will identify specific issues
2. **Check logs**: `sudo chatd-logs`
3. **Verify Docker**: `docker ps -a`
4. **Check permissions**: `ls -la /var/lib/chatd/`
5. **Reinstall scripts**: `sudo ./scripts/create-management-scripts.sh`

The migration scripts handle most edge cases automatically!
