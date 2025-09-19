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

# Logging Configuration
LOG_LEVEL=INFO                                # Optional: Logging level (INFO/DEBUG/etc)
LOG_FILE=chatd.log                            # Optional: Path to log file
LOG_MAX_BYTES=10485760                        # Optional: Max log file size (10MB)
LOG_BACKUP_COUNT=5                            # Optional: Number of backup logs to keep
```

## Running the Bot

### Direct Execution

You can run the bot directly:

```bash
# Make the script executable
chmod +x main.py

# Run the bot
./main.py
```

### Using the Run Script

The included `run_bot.sh` script provides a simple way to run the bot with automatic restart:

```bash
# Make the script executable
chmod +x run_bot.sh

# Run the bot with the script
./run_bot.sh
```

### As a systemd Service

For a more robust deployment, use the provided systemd service:

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

### Using Docker

You can also run the bot using Docker:

1. Build the Docker image:
    ```sh
    docker build -t chatd-internships .
    ```

2. Run the Docker container:
    ```sh
    docker run -d \
      --name chatd-internships \
      --restart unless-stopped \
      -v $(pwd)/.env:/app/.env \
      -v chatd-data:/app/Summer2026-Internships \
      -v chatd-logs:/app/logs \
      chatd-internships
    ```

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

```bash
python -m pytest tests/
```

## Log Management

The bot includes built-in log rotation via the `logging_utils.py` module:

- Automatically rotates logs when they reach the configured size
- Maintains the configured number of backup files
- Can be adjusted via environment variables

## Adjusting Log Levels at Runtime

You can change the log level at runtime by sending signals to the process:

- `SIGUSR1`: Increase verbosity (e.g., INFO → DEBUG)
- `SIGUSR2`: Decrease verbosity (e.g., DEBUG → INFO)

Example:
```bash
# Get the process ID
ps aux | grep main.py

# Increase verbosity
kill -SIGUSR1 <process_id>

# Decrease verbosity
kill -SIGUSR2 <process_id>
```

## Features

### Message Ordering and Processing

- **Chronological Processing**: Messages are processed in chronological order using a priority queue (heapq), ensuring posts appear in the correct sequence.
- **Date Filtering**: Only processes roles posted within the last 5 days to avoid spam from bulk updates.
- **Multi-Channel Support**: Can send messages to multiple Discord channels simultaneously.
- **Rate Limiting**: Includes built-in delays to prevent Discord API rate limiting.

### Reaction Processing

- **Interactive Messages**: The bot adds reactions to each message for user interaction.
- **DM Support**: When users react to a message, they receive a detailed DM with more job information.
- **Rich Formatting**: DMs include full job descriptions and application links.

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
