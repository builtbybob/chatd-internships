#!/bin/bash
#
# ChatD Bot Management Scripts
# These scripts help manage the dockerized ChatD Internships bot
#

# Build script - Build Docker image only with smart commit-based detection
create_chatd_build() {
    cat > /usr/local/bin/chatd-build << 'EOF'
#!/bin/bash
set -e

# Show help if requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "ChatD Bot Build Script"
    echo "Usage: chatd-build [BRANCH]"
    echo ""
    echo "Arguments:"
    echo "  BRANCH    Git branch to build from (optional)"
    echo ""
    echo "Environment Variables:"
    echo "  CHATD_BRANCH    Default branch to use if no argument provided"
    echo ""
    echo "Branch Resolution Priority:"
    echo "  1. Command line argument"
    echo "  2. CHATD_BRANCH environment variable"
    echo "  3. Default to 'main'"
    echo ""
    echo "Examples:"
    echo "  chatd-build               # Uses main (or CHATD_BRANCH if set)"
    echo "  chatd-build dev           # Uses dev branch"
    echo "  CHATD_BRANCH=dev chatd-build  # Uses dev branch"
    exit 0
fi

# Configuration
REPO_URL="https://github.com/builtbybob/chatd-internships.git"
BUILD_DIR="/tmp/chatd-build-$$"

# Branch priority: command line arg -> environment variable -> default to main
BRANCH="${1:-${CHATD_BRANCH:-main}}"

echo "🔄 Building ChatD Internships Bot..."
echo "📍 Repository: ${REPO_URL}"
echo "🌿 Branch: ${BRANCH}"

# Show branch source for clarity
if [[ -n "$1" ]]; then
    echo "   (specified via command line)"
elif [[ -n "$CHATD_BRANCH" ]]; then
    echo "   (from CHATD_BRANCH environment variable)"
else
    echo "   (default branch)"
fi

# Cleanup function
cleanup() {
    if [[ -d "$BUILD_DIR" ]]; then
        echo "🧹 Cleaning up build directory..."
        rm -rf "$BUILD_DIR"
    fi
}
trap cleanup EXIT

# Create clean build directory
echo "� Creating build directory: ${BUILD_DIR}"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Clone repository
echo "📡 Cloning repository..."
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" chatd-source
cd chatd-source

# Get current git commit hash
COMMIT_HASH=$(git rev-parse --short HEAD)
IMAGE_TAG="chatd-internships:${COMMIT_HASH}"
LATEST_TAG="chatd-internships:latest"

echo "📋 Current commit: ${COMMIT_HASH}"

# Check if image for this commit already exists
if docker image inspect "${IMAGE_TAG}" >/dev/null 2>&1; then
    echo "✅ Image for commit ${COMMIT_HASH} already exists!"
    echo "🏷️  Tagging as latest..."
    docker tag "${IMAGE_TAG}" "${LATEST_TAG}"
    echo "⚡ Build skipped - no changes detected"
    exit 0
fi

# Build new docker image with commit tag
echo "🐳 Building Docker image for commit ${COMMIT_HASH}..."
docker build -t "${IMAGE_TAG}" .

# Also tag as latest
echo "🏷️  Tagging as latest..."
docker tag "${IMAGE_TAG}" "${LATEST_TAG}"

echo "✅ Bot image built successfully!"
echo "📦 Image: ${IMAGE_TAG}"
echo "ℹ️  Use 'chatd deploy' to restart with the new image."
EOF
    chmod +x /usr/local/bin/chatd-build
}

# Deploy script - Restart service with existing image
create_chatd_deploy() {
    cat > /usr/local/bin/chatd-deploy << 'EOF'
#!/bin/bash
set -e

echo "🚀 Deploying ChatD Internships Bot..."

# Check if image exists
if ! docker image inspect chatd-internships:latest >/dev/null 2>&1; then
    echo "❌ Docker image 'chatd-internships:latest' not found!"
    echo "ℹ️  Run 'chatd build' first to create the image."
    exit 1
fi

# Restart the service if it's running
if systemctl is-active --quiet chatd-internships; then
    echo "🔄 Restarting service with new image..."
    systemctl restart chatd-internships
    echo "✅ Bot deployed successfully!"
else
    echo "🚀 Starting bot service..."
    systemctl start chatd-internships
    echo "✅ Bot started successfully!"
fi
EOF
    chmod +x /usr/local/bin/chatd-deploy
}

# Update script - Build and deploy with smart detection
create_chatd_update() {
    cat > /usr/local/bin/chatd-update << 'EOF'
#!/bin/bash
set -e

# Configuration
REPO_URL="https://github.com/builtbybob/chatd-internships.git"
BUILD_DIR="/tmp/chatd-build-$$"

# Branch priority: command line arg -> environment variable -> default to main
BRANCH="${1:-${CHATD_BRANCH:-main}}"

echo "🔄 Updating ChatD Internships Bot (build + deploy)..."
echo "📍 Repository: ${REPO_URL}"
echo "🌿 Branch: ${BRANCH}"

# Show branch source for clarity
if [[ -n "$1" ]]; then
    echo "   (specified via command line)"
elif [[ -n "$CHATD_BRANCH" ]]; then
    echo "   (from CHATD_BRANCH environment variable)"
else
    echo "   (default branch)"
fi

# Cleanup function
cleanup() {
    if [[ -d "$BUILD_DIR" ]]; then
        echo "🧹 Cleaning up build directory..."
        rm -rf "$BUILD_DIR"
    fi
}
trap cleanup EXIT

# Create clean build directory
echo "� Creating build directory: ${BUILD_DIR}"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Clone repository
echo "📡 Cloning repository..."
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" chatd-source
cd chatd-source

# Get current git commit hash
COMMIT_HASH=$(git rev-parse --short HEAD)
IMAGE_TAG="chatd-internships:${COMMIT_HASH}"
LATEST_TAG="chatd-internships:latest"

echo "📋 Current commit: ${COMMIT_HASH}"

# Check if image for this commit already exists
if docker image inspect "${IMAGE_TAG}" >/dev/null 2>&1; then
    echo "✅ Image for commit ${COMMIT_HASH} already exists!"
    echo "🏷️  Tagging as latest..."
    docker tag "${IMAGE_TAG}" "${LATEST_TAG}"
    echo "⚡ Build skipped - no changes detected"
else
    # Build new docker image with commit tag
    echo "🐳 Building Docker image for commit ${COMMIT_HASH}..."
    docker build -t "${IMAGE_TAG}" .
    
    # Also tag as latest
    echo "🏷️  Tagging as latest..."
    docker tag "${IMAGE_TAG}" "${LATEST_TAG}"
    echo "✅ Bot image built successfully!"
fi

# Restart the service if it's running
if systemctl is-active --quiet chatd-internships; then
    echo "🔄 Restarting service..."
    systemctl restart chatd-internships
    echo "✅ Bot updated and deployed!"
    echo "📦 Running: ${IMAGE_TAG}"
else
    echo "🚀 Starting bot service..."
    systemctl start chatd-internships
    echo "✅ Bot built and started!"
    echo "📦 Running: ${IMAGE_TAG}"
fi
EOF
    chmod +x /usr/local/bin/chatd-update
}

# Version script - Show version information and manage image versions
create_chatd_version() {
    cat > /usr/local/bin/chatd-version << 'EOF'
#!/bin/bash

show_usage() {
    echo "ChatD Bot Version Management"
    echo "Usage: chatd-version [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  show, current    Show currently running version"
    echo "  list             List all available image versions"
    echo "  images           Show Docker images with sizes"
    echo "  clean            Remove old unused images (keep last 5)"
    echo ""
    echo "Examples:"
    echo "  chatd-version                # Show current version"
    echo "  chatd-version list          # List all versions"
    echo "  chatd-version clean         # Clean old images"
}

show_current_version() {
    echo "🔍 Current ChatD Bot Version Information"
    echo "========================================"
    
    # Check if container is running
    if docker ps -q -f name=chatd-bot >/dev/null 2>&1; then
        CONTAINER_ID=$(docker ps -q -f name=chatd-bot)
        IMAGE_ID=$(docker inspect --format='{{.Image}}' $CONTAINER_ID 2>/dev/null)
        IMAGE_TAG=$(docker inspect --format='{{index .RepoTags 0}}' $IMAGE_ID 2>/dev/null || echo "Unknown")
        
        echo "📦 Running Image: $IMAGE_TAG"
        echo "🆔 Image ID: $(echo $IMAGE_ID | cut -c1-12)"
        echo "📅 Created: $(docker inspect --format='{{.Created}}' $IMAGE_ID 2>/dev/null | cut -c1-19)"
        
        # Try to extract commit hash from tag
        if [[ $IMAGE_TAG =~ chatd-internships:([a-f0-9]+) ]]; then
            COMMIT_HASH="${BASH_REMATCH[1]}"
            echo "🔗 Git Commit: $COMMIT_HASH"
            
            # Try to show commit info from GitHub API (requires curl)
            if command -v curl >/dev/null 2>&1; then
                REPO_API="https://api.github.com/repos/builtbybob/chatd-internships/commits/$COMMIT_HASH"
                COMMIT_INFO=$(curl -s "$REPO_API" 2>/dev/null | grep -o '"message":"[^"]*"' | cut -d'"' -f4 | head -1)
                if [[ -n "$COMMIT_INFO" ]]; then
                    echo "📝 Commit Info: $COMMIT_HASH $COMMIT_INFO"
                fi
            fi
        fi
    else
        echo "❌ ChatD bot container is not running"
    fi
    
    echo ""
}

list_versions() {
    echo "📋 Available ChatD Bot Image Versions"
    echo "====================================="
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" \
        --filter reference=chatd-internships \
        | head -20
    echo ""
}

clean_old_images() {
    echo "🧹 Cleaning old ChatD Bot images..."
    echo "Keeping the 5 most recent images..."
    
    # Get images sorted by creation date, skip the first 5 (most recent)
    OLD_IMAGES=$(docker images chatd-internships --format "{{.ID}}" | tail -n +6)
    
    if [ -n "$OLD_IMAGES" ]; then
        echo "Removing old images:"
        echo "$OLD_IMAGES" | while read image_id; do
            echo "  🗑️  Removing: $image_id"
            docker rmi "$image_id" 2>/dev/null || echo "    ⚠️  Could not remove $image_id (may be in use)"
        done
    else
        echo "✅ No old images to clean"
    fi
    echo ""
}

case "${1:-show}" in
    show|current|"")
        show_current_version
        ;;
    list)
        list_versions
        ;;
    images)
        list_versions
        ;;
    clean)
        clean_old_images
        ;;
    help|-h|--help)
        show_usage
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
EOF
    chmod +x /usr/local/bin/chatd-version
}

# Dynamic log level control script
create_chatd_loglevel() {
    cat > /usr/local/bin/chatd-loglevel << 'EOF'
#!/bin/bash
# ChatD Bot - Dynamic Log Level Control
# Change log levels without restarting the bot

CONTAINER_NAME="chatd-bot"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ ChatD bot container is not running"
    echo "   Start it with: chatd start"
    exit 1
fi

# Function to set log level
set_log_level() {
    local level="$1"
    
    # Write level to temp file and signal the container
    echo "${level}" | docker exec -i "${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
    
    # Send SIGHUP signal to trigger level change (using docker kill instead of exec kill)
    docker kill --signal=HUP "${CONTAINER_NAME}" > /dev/null
    
    echo "📝 Log level changed to: ${level}"
    echo "   View logs with: chatd-logs -f"
}

# Parse command line argument
case "${1:-}" in
    debug|DEBUG)
        set_log_level "DEBUG"
        echo "   🔍 Debug logging enabled - very verbose output"
        ;;
    info|INFO)
        set_log_level "INFO"
        echo "   ℹ️  Info logging enabled - normal operational messages"
        ;;
    warning|WARNING|warn|WARN)
        set_log_level "WARNING"
        echo "   ⚠️  Warning logging enabled - warnings and errors only"
        ;;
    error|ERROR)
        set_log_level "ERROR"
        echo "   ❌ Error logging enabled - errors and critical only"
        ;;
    critical|CRITICAL|crit|CRIT)
        set_log_level "CRITICAL"
        echo "   🚨 Critical logging enabled - critical errors only"
        ;;
    "")
        echo "Usage: chatd-loglevel <level>"
        echo ""
        echo "Available log levels:"
        echo "  debug    - Very verbose, shows all debug information"
        echo "  info     - Normal operations, startup/shutdown messages"
        echo "  warning  - Warnings and more severe messages only"
        echo "  error    - Error conditions and critical issues only"
        echo "  critical - Only critical system failures"
        echo ""
        echo "Current container status:"
        docker ps --format "  {{.Names}}: {{.Status}}" --filter name="${CONTAINER_NAME}"
        exit 1
        ;;
    *)
        echo "❌ Invalid log level: $1"
        echo "   Valid levels: debug, info, warning, error, critical"
        exit 1
        ;;
esac
EOF
    chmod +x /usr/local/bin/chatd-loglevel
}

# Logs script - View bot logs
create_chatd_logs() {
    cat > /usr/local/bin/chatd-logs << 'EOF'
#!/bin/bash

# Function to show usage
show_usage() {
    echo "Usage: chatd-logs [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --follow     Follow log output (like tail -f)"
    echo "  -n, --lines NUM  Show last NUM lines (default: 50)"
    echo "  --docker         Show Docker container logs instead of app logs"
    echo "  --system         Show systemd service logs"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  chatd-logs              # Show last 50 lines"
    echo "  chatd-logs -f           # Follow logs in real-time"
    echo "  chatd-logs -n 100       # Show last 100 lines"
    echo "  chatd-logs --docker     # Show Docker logs"
    echo "  chatd-logs --system     # Show systemd logs"
}

# Default values
FOLLOW=false
LINES=50
LOG_TYPE="app"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        --docker)
            LOG_TYPE="docker"
            shift
            ;;
        --system)
            LOG_TYPE="system"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Show logs based on type
case $LOG_TYPE in
    "app")
        if [[ "$FOLLOW" == "true" ]]; then
            echo "📋 Following application logs..."
            tail -f /var/lib/chatd/logs/chatd.log 2>/dev/null || echo "❌ No application logs found"
        else
            echo "📋 Last $LINES lines of application logs:"
            tail -n "$LINES" /var/lib/chatd/logs/chatd.log 2>/dev/null || echo "❌ No application logs found"
        fi
        ;;
    "docker")
        if [[ "$FOLLOW" == "true" ]]; then
            echo "🐳 Following Docker container logs..."
            docker logs -f chatd-bot 2>/dev/null || echo "❌ Container not running or not found"
        else
            echo "🐳 Last $LINES lines of Docker logs:"
            docker logs --tail "$LINES" chatd-bot 2>/dev/null || echo "❌ Container not running or not found"
        fi
        ;;
    "system")
        if [[ "$FOLLOW" == "true" ]]; then
            echo "⚙️  Following systemd service logs..."
            journalctl -f -u chatd-internships
        else
            echo "⚙️  Last $LINES lines of systemd logs:"
            journalctl -n "$LINES" -u chatd-internships
        fi
        ;;
esac
EOF
    chmod +x /usr/local/bin/chatd-logs
}

# Backup script - Backup bot data
create_chatd_backup() {
    cat > /usr/local/bin/chatd-backup << 'EOF'
#!/bin/bash
set -e

# Create backup with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/chatd_backup_$TIMESTAMP.tar.gz"

echo "💾 Creating backup of ChatD bot data..."

# Create compressed backup
tar -czf "$BACKUP_FILE" \
    -C /var/lib/chatd data \
    -C /etc/chatd .env \
    2>/dev/null || echo "⚠️  Some files may not exist yet"

if [[ -f "$BACKUP_FILE" ]]; then
    echo "✅ Backup created successfully:"
    echo "   📁 File: $BACKUP_FILE"
    echo "   📊 Size: $(du -h "$BACKUP_FILE" | cut -f1)"
    echo ""
    echo "💡 To restore this backup:"
    echo "   sudo tar -xzf $BACKUP_FILE -C /"
else
    echo "❌ Backup failed!"
    exit 1
fi
EOF
    chmod +x /usr/local/bin/chatd-backup
}

# Data inspection script
create_chatd_data() {
    cat > /usr/local/bin/chatd-data << 'EOF'
#!/bin/bash

echo "📊 ChatD Bot Data Status"
echo "========================"

# Bot Data Files
echo ""
echo "📁 Bot Data Files:"
if [[ -d "/var/lib/chatd/data" ]]; then
    ls -la /var/lib/chatd/data/ 2>/dev/null || echo "   (empty)"
else
    echo "   ❌ Data directory not found"
fi

# Repository Status
echo ""
echo "📚 Repository Status:"
if [[ -d "/var/lib/chatd/repo" ]]; then
    cd /var/lib/chatd/repo 2>/dev/null && {
        if [[ -d ".git" ]]; then
            echo "   📍 Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
            echo "   🔄 Last commit: $(git log -1 --pretty=format:'%h %s' 2>/dev/null || echo 'unknown')"
            echo "   📅 Last pull: $(stat -c %y .git/FETCH_HEAD 2>/dev/null || echo 'never')"
        else
            echo "   ❌ Not a git repository"
        fi
    } || echo "   ❌ Repository directory not accessible"
else
    echo "   ❌ Repository directory not found"
fi

# Container Status
echo ""
echo "🐳 Container Status:"
if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -q chatd-bot; then
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep chatd-bot
else
    echo "   ❌ Container not running"
fi

# Service Status
echo ""
echo "⚙️  Service Status:"
systemctl status chatd-internships --no-pager -l || echo "   ❌ Service status unknown"

# Recent Log Summary
echo ""
echo "📋 Recent Activity:"
if [[ -f "/var/lib/chatd/logs/chatd.log" ]]; then
    echo "   Last 5 log entries:"
    tail -5 /var/lib/chatd/logs/chatd.log | sed 's/^/   /'
else
    echo "   ❌ No log file found"
fi

# Disk Usage
echo ""
echo "💾 Disk Usage:"
echo "   Data: $(du -sh /var/lib/chatd 2>/dev/null | cut -f1 || echo 'unknown')"
echo "   Logs: $(du -sh /var/lib/chatd/logs 2>/dev/null | cut -f1 || echo 'unknown')"
EOF
    chmod +x /usr/local/bin/chatd-data
}

# Control script - Start/stop/restart with shortcuts
create_chatd_control() {
    cat > /usr/local/bin/chatd << 'EOF'
#!/bin/bash

show_usage() {
    echo "ChatD Bot Control Script"
    echo "Usage: chatd <command>"
    echo ""
    echo "Commands:"
    echo "  start      Start the bot service"
    echo "  stop       Stop the bot service"
    echo "  restart    Restart the bot service"
    echo "  status     Show service status"
    echo "  enable     Enable service to start on boot"
    echo "  disable    Disable service auto-start"
    echo "  logs       Show recent logs (alias for chatd-logs)"
    echo "  data       Show data status (alias for chatd-data)"
    echo "  backup     Create backup (alias for chatd-backup)"
    echo "  build      Build Docker image (alias for chatd-build)"
    echo "  deploy     Deploy with existing image (alias for chatd-deploy)"
    echo "  update     Build and deploy together (alias for chatd-update)"
    echo "  version    Show version information (alias for chatd-version)"
    echo ""
    echo "Examples:"
    echo "  chatd start           # Start the bot"
    echo "  chatd build           # Build new image"
    echo "  chatd build dev       # Build from specific branch"
    echo "  chatd deploy          # Deploy with existing image"
    echo "  chatd update          # Build and deploy together"
    echo "  chatd version         # Show current version"
    echo "  chatd logs -f         # Follow logs in real-time"
    echo "  chatd status          # Check if bot is running"
    echo ""
    echo "Environment Variables:"
    echo "  CHATD_BRANCH          # Default branch for build/update commands"
    echo "                        # Example: export CHATD_BRANCH=dev"
}

case "$1" in
    start)
        echo "🚀 Starting ChatD bot..."
        sudo systemctl start chatd-internships
        ;;
    stop)
        echo "⏹️  Stopping ChatD bot..."
        sudo systemctl stop chatd-internships
        ;;
    restart)
        echo "🔄 Restarting ChatD bot..."
        sudo systemctl restart chatd-internships
        ;;
    status)
        systemctl status chatd-internships --no-pager
        ;;
    enable)
        echo "✅ Enabling ChatD bot auto-start..."
        sudo systemctl enable chatd-internships
        ;;
    disable)
        echo "❌ Disabling ChatD bot auto-start..."
        sudo systemctl disable chatd-internships
        ;;
    logs)
        shift
        chatd-logs "$@"
        ;;
    data)
        chatd-data
        ;;
    backup)
        chatd-backup
        ;;
    build)
        chatd-build
        ;;
    deploy)
        chatd-deploy
        ;;
    update)
        chatd-update
        ;;
    version)
        shift
        chatd-version "$@"
        ;;
    ""|help|-h|--help)
        show_usage
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
EOF
    chmod +x /usr/local/bin/chatd
}

# Main execution
echo "Creating ChatD management scripts..."

create_chatd_build
echo "✅ Created chatd-build"

create_chatd_deploy
echo "✅ Created chatd-deploy"

create_chatd_update
echo "✅ Created chatd-update"

create_chatd_version
echo "✅ Created chatd-version"

create_chatd_loglevel
echo "✅ Created chatd-loglevel"

create_chatd_logs
echo "✅ Created chatd-logs" 

create_chatd_backup
echo "✅ Created chatd-backup"

create_chatd_data
echo "✅ Created chatd-data"

create_chatd_control
echo "✅ Created chatd (main control script)"

echo ""
echo "🎉 All management scripts created successfully!"
echo ""
echo "Available commands:"
echo "  chatd start/stop/restart - Control the bot"
echo "  chatd-logs -f           - Follow logs in real-time"
echo "  chatd-data              - Check bot data status"
echo "  chatd-backup            - Create data backup"
echo "  chatd-build             - Build Docker image with smart detection"
echo "  chatd-deploy            - Deploy with existing image"
echo "  chatd-update            - Build and deploy together"
echo "  chatd-version           - Show version and manage images"
echo "  chatd-loglevel <level>  - Change log level without restart"
