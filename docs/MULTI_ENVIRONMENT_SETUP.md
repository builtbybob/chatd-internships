# Multi-Environment Setup Guide

## Overview

The ChatD system now supports multiple isolated environments using the generalized `setup-chatd-environment.sh` script. This allows you to run multiple ChatD instances for different purposes:

- **Production**: `/opt/chatd` (existing)
- **Development**: `/opt/thatd-internships` 
- **New Grad Roles**: `/opt/newgrad-roles`
- **Seasonal**: `/opt/chatd-fall2025`
- **Custom**: Any name you choose

## Quick Start

### Prerequisites
- **Discord Bot Token**: Create a bot at https://discord.com/developers/applications
- **Channel IDs**: Right-click on Discord channels → "Copy ID" (requires Developer Mode)

### 1. Create a New Environment

```bash
sudo ./scripts/setup-chatd-environment.sh <environment-name>
```

The script will prompt you for:
- **Discord Bot Token** (from Discord Developer Portal)
- **Channel IDs** (comma-separated list)
- **Database Password** (auto-generated)

Examples: `chatd-internships`, `chatd-newgrad`

### 2. Start the Environment

```bash
# Everything is configured automatically!
<env-name> start
<env-name> enable  # Enable auto-start on boot
<env-name> status  # Check status
```

## Environment Naming

- **Environment name**: Used for all components (thatd-internships)
- **Directory**: `/opt/<env-name>/`
- **Containers**: `<env-name>-postgres`, `<env-name>-bot`
- **Database**: `<env_name_underscores>` (thatd_internships)
- **Network**: `<env-name>-network`
- **Volumes**: `<env-name>_postgres_data`, etc.
- **Service**: `<env-name>.service`
- **Command**: `/usr/local/bin/<env-name>`

## Management Commands

Each environment gets its own management command:

```bash
# Environment status and control
<environment-name> status
<environment-name> start
<environment-name> stop
<environment-name> restart

# Logs and monitoring
<environment-name> logs           # All logs
<environment-name> logs bot       # Bot logs only
<environment-name> logs postgres  # Database logs only

# Container access
<environment-name> shell          # Bot container shell
<environment-name> shell postgres # Database container shell
<environment-name> db             # PostgreSQL command line

# Maintenance
<environment-name> build          # Build containers
<environment-name> update         # Pull, build, restart
<environment-name> cleanup        # Clean up Docker resources
```

## Automatic Features

### Port Assignment
- **PostgreSQL**: Automatically assigned unique ports (5433+)
- **Web interfaces**: Automatically assigned unique ports (8081+)
- **No conflicts**: Script checks for available ports

### Container Isolation
- **Separate networks**: Each environment has its own Docker network
- **Separate volumes**: Independent data storage per environment
- **Separate databases**: Completely isolated PostgreSQL instances

### Performance Optimization
- **Section 4.1 settings**: All environments include optimized message posting delays
- **Configurable**: Can be tuned per environment in `.env` file

## Environment Examples

```bash
# Fully automated setup - just run and follow prompts!
sudo ./scripts/setup-chatd-environment.sh <environment-name>
<environment-name> start
<environment-name> status
```

## Configuration Templates

The script automatically generates optimized configuration files:

### Docker Compose
- Environment-specific container names
- Unique port assignments
- Isolated networks and volumes
- Database environment variables

### Environment Variables
- Discord bot configuration
- Database connection settings
- Performance optimizations (Section 4.1)
- Environment-specific settings

### Systemd Service
- Auto-start capability
- Proper dependencies
- Environment-specific naming

## Resource Usage

With 69GB available disk space, we can comfortably run multiple environments:

- **Per environment**: ~2-3GB (containers + data)
- **Database**: ~500MB-1GB per environment
- **Logs**: ~100-500MB per environment
- **Total capacity**: 5-10+ environments easily supported

## Security

- **Isolated networks**: No cross-environment communication
- **Separate databases**: Independent schemas and users
- **Secure configuration**: Environment files have restricted permissions (600)
- **Independent tokens**: Each environment uses its own Discord bot

## Troubleshooting

### Check Environment Status
```bash
<env-name> status
docker ps | grep <env-name>
docker network ls | grep <env-name>
```

### View Logs
```bash
<env-name> logs
journalctl -u <env-name>.service
```

### Database Issues
```bash
<env-name> db
<env-name> shell postgres
```

### Port Conflicts
The script automatically assigns unique ports, but you can check:
```bash
ss -tuln | grep 5432  # Check PostgreSQL ports
ss -tuln | grep 8080  # Check web ports
```

## Next Steps

1. **Create development environment**: Choose any name (e.g., `thatd-internships`)
2. **Test Section 4.1 optimizations**: In isolated environment
3. **Configure separate Discord bots**: For each environment
4. **Set up monitoring**: Independent per environment
5. **Future environments**: Easy to add as needed