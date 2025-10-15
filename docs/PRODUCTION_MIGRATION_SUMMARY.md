# Production Migration Summary: Making /opt/thatd the New Production Environment

## Overview

Instead of adding reactions to existing messages via Discord API, we're taking a simpler approach:
- **Make `/opt/thatd` the new production environment** (it already has reaction support)
- **Migrate only the database data** from `/opt/chatd` (old production)
- **Switch Discord configuration** to use production bot and channels
- **Add reactions to production messages** using the existing reaction script

This approach avoids complex Discord API rate limiting and provides a cleaner migration path.

## Migration Plan

### Step 1: Backup Current Development Data

Before we replace anything, backup the current development data for future use:

```bash
# Create backup directory
BACKUP_DIR="/tmp/thatd_dev_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup dev message_tracking table
cd /opt/thatd
sudo docker-compose exec -T thatd-postgres pg_dump \
    -U thatd -d thatd \
    --table=message_tracking \
    --data-only \
    --inserts \
    --no-owner \
    --no-privileges > "$BACKUP_DIR/dev_message_tracking.sql"

# Backup dev student_applications table (test data)
sudo docker-compose exec -T thatd-postgres pg_dump \
    -U thatd -d thatd \
    --table=student_applications \
    --data-only \
    --inserts \
    --no-owner \
    --no-privileges > "$BACKUP_DIR/dev_student_applications.sql"

# Backup current .env file
cp /opt/thatd/.env "$BACKUP_DIR/dev_env_backup"
```

### Step 2: Export Production Data

Export the message tracking data from the old production environment:

```bash
# Export production message_tracking
cd /opt/chatd
sudo docker-compose exec -T chatd-postgres pg_dump \
    -U chatd -d chatd \
    --table=message_tracking \
    --data-only \
    --inserts \
    --no-owner \
    --no-privileges > /tmp/prod_message_tracking.sql
```

**Expected data**: ~1,816 message tracking entries from production

### Step 3: Stop Development Bot

Stop the bot before making database and configuration changes:

```bash
cd /opt/thatd

# Stop the bot to prevent conflicts during migration
sudo docker-compose stop thatd-bot
```

### Step 4: Clear and Import to New Production

Replace the development data with production data:

```bash
cd /opt/thatd

# Clear current dev data
sudo docker-compose exec -T thatd-postgres psql -U thatd -d thatd -c "DELETE FROM student_applications;"
sudo docker-compose exec -T thatd-postgres psql -U thatd -d thatd -c "DELETE FROM message_tracking;"

# Import production message tracking
sudo docker-compose exec -T thatd-postgres psql -U thatd -d thatd < /tmp/prod_message_tracking.sql

# Verify import
sudo docker-compose exec -T thatd-postgres psql -U thatd -d thatd -c "SELECT COUNT(*) FROM message_tracking;"
sudo docker-compose exec -T thatd-postgres psql -U thatd -d thatd -c "SELECT COUNT(*) FROM student_applications;"
```

**Expected result**: 1,816 messages, 0 applications

### Step 5: Update Discord Configuration

Update `/opt/thatd/.env` to use production Discord settings:

```bash
# Edit the environment file
nano /opt/thatd/.env

# Required changes:
# DISCORD_TOKEN=<production_bot_token>
# CHANNEL_ID=<production_channel_id>
# Any other channel IDs that need updating
```

**Important**: Make sure to use the production Discord bot token and the production channel IDs.

### Step 6: Test the New Production Environment

```bash
cd /opt/thatd

# Start services with new configuration
sudo docker-compose up -d

# Check logs to ensure bot connects successfully
sudo docker-compose logs -f thatd-bot

# Verify database connectivity
sudo docker-compose exec thatd-postgres psql -U thatd -d thatd -c "SELECT COUNT(*) FROM message_tracking;"
```

### Step 7: Add Reactions to Existing Production Messages

Now that `/opt/thatd` is connected to the production Discord channel with the production message tracking data, add reactions to the existing messages:

```bash
cd /opt/thatd

# Copy the migration script from the development repository
cp /home/rbarton/chatd-internships/scripts/add_reactions_to_existing_messages.py scripts/

# Test with dry run first (using the current environment's Python)
/opt/thatd/.venv/bin/python scripts/add_reactions_to_existing_messages.py --dry-run --batch-size 25 --verbose

# Run actual migration with conservative settings
/opt/thatd/.venv/bin/python scripts/add_reactions_to_existing_messages.py --batch-size 25 --delay 2.0 --verbose
```

**Expected timeline**: 30-45 minutes to process ~1,816 messages

### Step 8: Create New Development Environment

Once production is working, create a fresh development environment:

```bash
# Create new development directory
sudo mkdir -p /opt/bratd
sudo chown $USER:$USER /opt/bratd

# Copy code and configuration from new production
cp -r /opt/thatd/* /opt/bratd/
cd /opt/bratd

# Update .env for development settings
# - Use development Discord bot token
# - Use development channel IDs
# - Update database name/credentials if needed

# Start development environment
sudo docker-compose up -d
```

## Current Environment Status

| Environment | Path | Purpose | Discord Channel | Database |
|-------------|------|---------|----------------|-----------|
| Old Production | `/opt/chatd` | **To be decommissioned** | Production channel | 1,816 messages, production applications |
| New Production | `/opt/thatd` | **Current production** | Production channel (after config update) | Production messages, clean applications |
| New Development | `/opt/bratd` | **Future development** | Development channel | Fresh development data |

## Files and Scripts

### Required Script
- **`scripts/add_reactions_to_existing_messages.py`** - Adds reactions to existing Discord messages

### Documentation
- **`docs/REACTION_MIGRATION.md`** - Detailed reaction migration guide
- **`docs/PRODUCTION_MIGRATION_SUMMARY.md`** - This step-by-step guide

## Advantages of This Approach

✅ **No Discord API complexity** - Just database operations until the final step  
✅ **Tested environment** - `/opt/thatd` already has working reaction support  
✅ **Clean data** - Fresh start for application tracking without test data  
✅ **Reversible** - Backups allow restoration if needed  
✅ **Gradual process** - Each step can be verified before proceeding  

## Verification Steps

After each major step:

1. **After database migration**: Verify message counts match
2. **After Discord config**: Verify bot connects to correct channels
3. **After reaction migration**: Spot-check messages have ❓ and 📝 reactions
4. **After new dev setup**: Verify development environment works independently

## Timeline Estimate

- **Steps 1-2** (Backup and export): 5-10 minutes
- **Steps 3-5** (Stop bot, database migration, config): 10-15 minutes
- **Step 6** (Test new production): 5-10 minutes  
- **Step 7** (Reaction migration): 30-45 minutes
- **Step 8** (New dev environment): 10-15 minutes

**Total**: ~1.5-2 hours for complete migration

## Rollback Plan

If issues arise:

1. **Restore dev data**: Use backups from Step 1
2. **Revert configuration**: Restore original `.env` file
3. **Switch back**: Temporarily use `/opt/chatd` while troubleshooting

The old production environment remains untouched until migration is confirmed successful.