![ChatD Internships Banner](ChatdInternshipsBanner.png)

# Ch@d Internships Bot
[![Tests](https://github.com/builtbybob/chatd-internships/actions/workflows/coverage.yml/badge.svg)](https://github.com/builtbybob/chatd-internships/actions)

## Overview

This project is a Discord bot designed to monitor a GitHub repository for new internship postings and send formatted messages to a specified Discord channel. The bot performs the following tasks:

1. Clones or updates the specified GitHub repository.
2. Reads a JSON file containing internship listings.
3. Compares the new listings with previously stored data.
4. Sends formatted messages to a Discord channel for any new visible and active roles.
5. Adds reactions to messages for user interaction (configurable via `ENABLE_REACTIONS`).
6. Sends detailed job information DMs when users react to a message (when enabled).

## Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Discord bot with Message Content Intent and Reactions Intent enabled
- One or more Discord channel IDs

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/builtbybob/chatd-internships.git
    cd chatd-internships
    ```

2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up your Discord bot:
    - Create a new bot on the [Discord Developer Portal](https://discord.com/developers/applications).
    - Enable the "Message Content Intent" in the Bot section.
    - Copy the bot token and set it in your `.env` file.
    - Get the channel IDs where you want the bot to send messages and set them in `CHANNEL_IDS`.

### Configuration

The bot uses environment variables for configuration. Copy the `.env.example` file to `.env` and configure:

```ini
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here      # Required: Your Discord bot token
CHANNEL_IDS=123456789,987654321               # Required: Comma-separated list of channel IDs

# Repository Configuration
REPO_URL=https://github.com/SimplifyJobs/Summer2026-Internships.git  # Optional: Default shown
LOCAL_REPO_PATH=Summer2026-Internships        # Optional: Local path for the repo

# Bot Configuration
MAX_RETRIES=3                                 # Optional: Max retries for failed channels
CHECK_INTERVAL_MINUTES=1                      # Optional: Minutes between repo checks
ENABLE_REACTIONS=false                        # Optional: Enable reaction features (default: true)

# Logging Configuration
LOG_LEVEL=INFO                                # Optional: Logging level (INFO/DEBUG/etc)
LOG_FILE=chatd.log                            # Optional: Path to log file
LOG_MAX_BYTES=10485760                        # Optional: Max log file size (10MB)
LOG_BACKUP_COUNT=5                            # Optional: Number of backup logs to keep
```

## Running the Bot

### Production Deployment (Recommended)

For production environments, use the Docker + systemd deployment:

```bash
# Start the production service
sudo systemctl start chatd-internships

# Check status
chatd status

# Follow logs
chatd logs -f
```

See the "Production Deployment with Docker + systemd" section below for full setup instructions.

### Development and Testing

#### Direct Execution

You can run the bot directly:

```bash
# Make the script executable
chmod +x main.py

# Run the bot
./main.py
```

#### Using the Run Script (Development)

The included `run_bot.sh` script provides a simple way to run the bot with automatic restart:

```bash
# Make the script executable
chmod +x run_bot.sh

# Run the bot with the script
./run_bot.sh
```

#### Legacy systemd Service (Without Docker)

For non-Docker deployments, use the basic systemd service:

1. Copy the service file to the systemd directory:
    ```sh
    sudo cp chatd-internships.service /etc/systemd/system/
    ```

2. Edit the service file to update paths and user if needed:
    ```sh
    sudo nano /etc/systemd/system/chatd-internships.service
    ```

3. Enable and start the service:
    ```sh
    sudo systemctl daemon-reload
    sudo systemctl enable chatd-internships
    sudo systemctl start chatd-internships
    ```

4. Check the service status:
    ```sh
    sudo systemctl status chatd-internships
    ```

### Production Deployment with Docker + systemd

The recommended production deployment uses Docker with systemd for robust service management:

#### Prerequisites for Production

1. Install Docker:
    ```sh
    sudo apt update && sudo apt install -y docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
    ```

2. Create the production configuration:
    ```sh
    sudo mkdir -p /etc/chatd
    sudo cp .env /etc/chatd/.env
    sudo chmod 600 /etc/chatd/.env
    ```

3. Set up the management scripts:
    ```sh
    sudo bash scripts/create-management-scripts.sh
    ```

4. Set up the systemd service:
    ```sh
    sudo cp chatd-internships.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable chatd-internships
    ```

#### Initial Deployment

```sh
# Build the Docker image
sudo chatd build

# Start the service
sudo systemctl start chatd-internships

# Check status
chatd status
```

#### Management Scripts

The deployment includes management scripts for easy administration:

```sh
# Check service status
chatd status

# View logs
chatd logs -f              # Follow logs in real-time
chatd logs -n 100          # Show last 100 lines

# Service control
chatd start/stop/restart   # Control the service

# Dynamic log level control (NEW)
chatd-loglevel debug       # Enable debug logging for troubleshooting
chatd-loglevel info        # Normal operational logging
chatd-loglevel warning     # Show warnings and errors only
chatd-loglevel error       # Show errors only
chatd-loglevel critical    # Show critical errors only

# Build and deployment (NEW - Optimized Workflow)
chatd build                # Build Docker image only
chatd deploy               # Deploy with existing image (fast ~8 seconds)
chatd update               # Build and deploy together

# Maintenance
chatd backup               # Create data backup
chatd data                 # Show data status
```

**New Optimized Deployment Workflow:**
- **Development**: Use `chatd build` once, then `chatd deploy` for quick iterations
- **Production Updates**: Use `chatd update` for full rebuild and deployment
- **Performance**: Deployment time reduced from 4+ minutes to ~8 seconds

#### Docker Volumes

The production setup uses persistent volumes:
- `/var/lib/chatd/data`: Bot data and storage
- `/var/lib/chatd/repo`: GitHub repository cache
- `/var/lib/chatd/logs`: Application logs

#### Manual Docker Usage

For development or manual deployment:

```sh
# Build the image
docker build -t chatd-internships:latest .

# Run manually (or use the optimized commands above)
docker run -d \
  --name chatd-bot \
  --env-file /etc/chatd/.env \
  --restart unless-stopped \
  -v /var/lib/chatd/data:/app/data \
  -v /var/lib/chatd/repo:/app/Summer2026-Internships \
  -v /var/lib/chatd/logs:/app/logs \
  chatd-internships:latest
```

**Note**: The production systemd service no longer rebuilds Docker images on startup for faster deployment. Use the management commands above for optimal workflow.

## Development

The bot is organized into modules:

- `chatd/config.py`: Configuration management
- `chatd/logging_utils.py`: Logging setup and management
- `chatd/repo.py`: GitHub repository handling
- `chatd/messages.py`: Message formatting
- `chatd/storage.py`: Data persistence
- `chatd/bot.py`: Discord bot and event handlers
- `main.py`: Entry point

### Running Tests

The project uses unittest for testing:

```bash
# Run all tests
python -m unittest discover tests/

# Run specific test modules
python -m unittest tests.test_bot
python -m unittest tests.test_config

# Run with verbose output
python -m unittest discover tests/ -v
```

## Log Management

The bot includes built-in log rotation via the `logging_utils.py` module:

- Automatically rotates logs when they reach the configured size
- Maintains the configured number of backup files
- Can be adjusted via environment variables

## 🔧 Troubleshooting & Log Management

### Dynamic Log Level Control

The bot supports **instant log level changes without restart**, perfect for production debugging:

```bash
# Enable debug logging for detailed troubleshooting
sudo chatd-loglevel debug

# View detailed logs in real-time
sudo chatd-logs -f

# Return to normal logging after debugging  
sudo chatd-loglevel info
```

**Available Log Levels:**
- `debug`: Maximum verbosity - shows all operations, git commands, API calls
- `info`: Normal operations - startup, shutdown, role processing
- `warning`: Warnings and errors only - for quiet production monitoring
- `error`: Error conditions only - for minimal logging
- `critical`: Critical failures only - for emergency situations

**Use Cases:**
- **Production Issues**: Instantly enable debug logging to investigate problems
- **Performance Monitoring**: Use warning level for clean production logs
- **Development**: Use debug level to see detailed operation flow
- **Troubleshooting**: No service restart required - maintain uptime while debugging

### Log Rotation

## Features

### Message Ordering and Processing

- **Chronological Processing**: Messages are processed in chronological order using a priority queue (heapq), ensuring posts appear in the correct sequence.
- **Date Filtering**: Only processes roles posted within the last 5 days to avoid spam from bulk updates.
- **Multi-Channel Support**: Can send messages to multiple Discord channels simultaneously.
- **Rate Limiting**: Includes built-in delays to prevent Discord API rate limiting.

### Reaction Processing (Optional Feature)

- **Configurable Reactions**: Use `ENABLE_REACTIONS=false` to disable reaction features for stability
- **Interactive Messages**: When enabled, the bot adds reactions to each message for user interaction
- **DM Support**: When users react to a message, they receive a detailed DM with more job information
- **Rich Formatting**: DMs include full job descriptions and application links

### Error Handling and Recovery

- **Channel Recovery**: Automatically retries failed channel messages up to configured MAX_RETRIES.
- **Channel Health Tracking**: Maintains a list of failed channels to avoid repeated failures.
- **Permission Handling**: Properly handles Discord permission errors and channel access issues.
- **Graceful Shutdown**: Handles SIGINT and SIGTERM signals for clean shutdown.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

### Core Functions

#### Repository Management
- `clone_or_update_repo()`: Manages the local copy of the internships repository.
- `read_json()`: Parses the internship listings file.

#### Message Processing
- `format_message(role)`: Creates formatted Discord messages from role data.
- `normalize_role_key(role)`: Generates stable keys for role comparison.
- `compare_roles(old_role, new_role)`: Detects changes in role attributes.

#### Discord Integration
- `send_message(message, channel_id, role_key)`: Sends a message to a single channel.
- `send_messages_to_channels(message, role_key)`: Distributes messages to all configured channels.
- `check_for_new_roles()`: Main update detection and message dispatch logic.

### Scheduling

The bot checks for updates at configurable intervals (default: 1 minute) using the `schedule` library. The check interval can be adjusted using the `CHECK_INTERVAL_MINUTES` environment variable.
