#!/bin/bash

# Script to sync the internships repository and update previous_data.json
# This prevents message replay by setting the baseline to current or specified commit
# Usage: ./sync-repo-data.sh [commit_hash]
#   e.g. ./sync-repo-data.sh abc123def456  # Sync to specific commit
#        ./sync-repo-data.sh              # Sync to latest (git pull)

# Configuration
HOST_REPO_DIR="/var/lib/chatd/repo"
LISTINGS_PATH=".github/scripts/listings.json"
DATA_DIR="/var/lib/chatd/data"
PREVIOUS_DATA_FILE="$DATA_DIR/previous_data.json"
COMMIT_HASH="$1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Check if running as root (needed for file permissions)
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root (use sudo)"
    log_info "Example: sudo ./scripts/sync-repo-data.sh"
    exit 1
fi

# Check if directories exist
if [ ! -d "$HOST_REPO_DIR" ]; then
    log_error "Repository directory $HOST_REPO_DIR does not exist"
    log_info "Please ensure the bot is properly installed and the repository is cloned"
    exit 1
fi

if [ ! -d "$DATA_DIR" ]; then
    log_error "Data directory $DATA_DIR does not exist"
    log_info "Please ensure the bot is properly installed"
    exit 1
fi

# Save current directory
ORIGINAL_DIR=$(pwd)

# Navigate to repository directory
cd "$HOST_REPO_DIR" || {
    log_error "Failed to navigate to $HOST_REPO_DIR"
    exit 1
}

# Check if it's a git repository
if [ ! -d ".git" ]; then
    log_error "$HOST_REPO_DIR is not a git repository"
    log_info "Please ensure the repository is properly cloned"
    exit 1
fi

log_info "Syncing repository data to prevent message replay..."

# Stop the bot service if running
if systemctl is-active --quiet chatd-internships; then
    log_info "Stopping chatd-internships service..."
    systemctl stop chatd-internships
    SERVICE_WAS_RUNNING=true
else
    SERVICE_WAS_RUNNING=false
fi

# Sync repository
if [ -n "$COMMIT_HASH" ]; then
    # Sync to specific commit
    log_info "Syncing to commit: $COMMIT_HASH"
    
    # Fetch latest changes first
    if ! git fetch origin; then
        log_error "Failed to fetch from origin"
        exit 1
    fi
    
    # Reset to specific commit
    if ! git reset --hard "$COMMIT_HASH"; then
        log_error "Failed to reset to commit $COMMIT_HASH"
        log_info "Please verify the commit hash is valid"
        exit 1
    fi
    
    log_success "Repository synced to commit $COMMIT_HASH"
else
    # Sync to latest
    log_info "Syncing to latest version (git pull)..."
    
    if ! git pull origin main; then
        log_error "Failed to pull latest changes"
        exit 1
    fi
    
    CURRENT_COMMIT=$(git rev-parse HEAD)
    log_success "Repository synced to latest commit: $CURRENT_COMMIT"
fi

# Verify listings.json exists
if [ ! -f "$LISTINGS_PATH" ]; then
    log_error "Listings file not found: $LISTINGS_PATH"
    log_info "Please verify the repository structure is correct"
    exit 1
fi

# Copy listings.json to previous_data.json
log_info "Updating previous_data.json to prevent message replay..."
if ! cp "$LISTINGS_PATH" "$PREVIOUS_DATA_FILE"; then
    log_error "Failed to copy $LISTINGS_PATH to $PREVIOUS_DATA_FILE"
    exit 1
fi

# Set correct ownership
chown 1000:1000 "$PREVIOUS_DATA_FILE"

# Clear message tracking to start fresh
log_info "Clearing message tracking..."
echo '{}' > "$DATA_DIR/message_tracking.json"
chown 1000:1000 "$DATA_DIR/message_tracking.json"

# Show file sizes for verification
LISTINGS_SIZE=$(stat -c%s "$LISTINGS_PATH")
PREVIOUS_SIZE=$(stat -c%s "$PREVIOUS_DATA_FILE")

log_success "Data sync completed successfully!"
log_info "Listings file size: $LISTINGS_SIZE bytes"
log_info "Previous data size: $PREVIOUS_SIZE bytes"

if [ "$LISTINGS_SIZE" -eq "$PREVIOUS_SIZE" ]; then
    log_success "File sizes match - no messages should be replayed"
else
    log_warning "File sizes differ - this may indicate an issue"
fi

# Restart service if it was running
if [ "$SERVICE_WAS_RUNNING" = true ]; then
    log_info "Restarting chatd-internships service..."
    systemctl start chatd-internships
    log_success "Service restarted"
else
    log_info "Service was not running - start manually when ready"
fi

# Return to original directory
cd "$ORIGINAL_DIR" || exit 1

log_success "Repository sync complete!"
log_info "The bot will now use the current repository state as baseline"
log_info "Monitor logs with: docker logs -f chatd-bot"