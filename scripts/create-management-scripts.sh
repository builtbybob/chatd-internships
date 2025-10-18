#!/bin/bash

# Disk usage and image status script
create_chatd_disk() {
    cat > /usr/local/bin/chatd-disk << 'EOF'
#!/bin/bash

DISK_USAGE=$(df --output=pcent / | tail -1 | tr -dc '0-9')
AVAILABLE=$(df --output=avail / | tail -1)
TOTAL=$(df --output=size / | tail -1)
IMAGES=$(docker images chatd-internships --format "{{.Tag}} {{.Size}}" | grep -v latest)
IMAGE_COUNT=$(docker images chatd-internships --format "{{.Tag}}" | grep -v latest | wc -l)
IMAGE_SIZE=$(docker images chatd-internships --format "{{.Size}}" | grep -v latest | awk '{s+=$1} END {print s}')

echo "💾 Disk Usage: ${DISK_USAGE}% used, $((AVAILABLE/1024)) MB free, $((TOTAL/1024)) MB total"
echo "📦 ChatD images: $IMAGE_COUNT images"
docker images chatd-internships --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

if [ "$DISK_USAGE" -ge 90 ]; then
    echo "🚨 ALERT: Disk usage above 90%! Emergency cleanup recommended."
elif [ "$DISK_USAGE" -ge 80 ]; then
    echo "⚠️ Warning: Disk usage at ${DISK_USAGE}%. Consider manual cleanup."
fi

# Prometheus-style metrics for future monitoring
if [[ "$1" == "--metrics" ]]; then
    echo "chatd_disk_free_bytes $((AVAILABLE*1024))"
    echo "chatd_disk_used_percent $DISK_USAGE"
    echo "chatd_image_count $IMAGE_COUNT"
fi
EOF
    chmod +x /usr/local/bin/chatd-disk
}
# Manual Docker image cleanup script
create_chatd_cleanup() {
    cat > /usr/local/bin/chatd-cleanup << 'EOF'
#!/bin/bash
set -e

RETENTION_COUNT=${CHATD_DOCKER_RETENTION:-3}
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --count)
            RETENTION_COUNT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: chatd-cleanup [--count N] [--dry-run]"
            echo "  --count N   Keep N images (default: 3)"
            echo "  --dry-run   Preview images that would be deleted"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🧹 Manual Docker image cleanup..."
echo "📊 Retention policy: keeping $RETENTION_COUNT images (current + rollback options)"

IMAGE_TAGS=$(docker images chatd-internships --format "{{.Tag}}" | grep -v latest)
TO_DELETE=$(echo "$IMAGE_TAGS" | tail -n +$((RETENTION_COUNT + 1)))

if [[ "$DRY_RUN" == "true" ]]; then
    if [[ -z "$TO_DELETE" ]]; then
        echo "✅ No images to delete."
    else
        echo "🗑️  Images that would be deleted:"
        echo "$TO_DELETE" | while read tag; do
            echo "  chatd-internships:$tag"
        done
    fi
    exit 0
fi

# Disk space monitoring logic
DISK_USAGE=$(df --output=pcent / | tail -1 | tr -dc '0-9')
AVAILABLE=$(df --output=avail / | tail -1)
if [ "$DISK_USAGE" -ge 90 ]; then
    echo "⚠️ Disk usage above 90%. Running emergency cleanup..."
    sudo chatd-prune
elif [ "$DISK_USAGE" -ge 80 ]; then
    echo "⚠️ Warning: Disk usage at ${DISK_USAGE}%. Consider manual cleanup."
fi
if [ "$AVAILABLE" -lt $((1024 * 1024)) ]; then
    echo "❌ Not enough disk space to build new images. Aborting."
    exit 1
fi

if [[ -z "$TO_DELETE" ]]; then
    echo "✅ No images to delete."
else
    echo "$TO_DELETE" | while read tag; do
        if [[ -n "$tag" ]]; then
            echo "🗑️  Removing old image: chatd-internships:$tag"
            docker rmi "chatd-internships:$tag" 2>/dev/null || true
        fi
    done
fi

echo "✅ Cleanup complete. Retained $RETENTION_COUNT images."
EOF
    chmod +x /usr/local/bin/chatd-cleanup
}

# List Docker images script
create_chatd_images() {
    cat > /usr/local/bin/chatd-images << 'EOF'
#!/bin/bash
echo "📋 ChatD Docker Images (chatd-internships)"
docker images chatd-internships --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
EOF
    chmod +x /usr/local/bin/chatd-images
}

# Aggressive prune script (keep only latest)
create_chatd_prune() {
    cat > /usr/local/bin/chatd-prune << 'EOF'
#!/bin/bash
set -e

echo "🧨 Aggressive Docker image prune: keeping only the latest image..."
LATEST_TAG=$(docker images chatd-internships --format "{{.Tag}}" | grep -v latest | head -n 1)
TO_DELETE=$(docker images chatd-internships --format "{{.Tag}}" | grep -v latest | tail -n +2)

if [[ -z "$LATEST_TAG" ]]; then
    echo "❌ No images found to retain."
    exit 1
fi

if [[ -z "$TO_DELETE" ]]; then
    echo "✅ Only the latest image exists. No images to delete."
else
    echo "$TO_DELETE" | while read tag; do
        if [[ -n "$tag" ]]; then
            echo "🗑️  Removing old image: chatd-internships:$tag"
            docker rmi "chatd-internships:$tag" 2>/dev/null || true
        fi
    done
fi

echo "✅ Prune complete. Retained latest image: chatd-internships:$LATEST_TAG"
EOF
    chmod +x /usr/local/bin/chatd-prune
}
#!/bin/bash
#
# ChatD Bot Management Scripts
# These scripts help manage the dockerized ChatD Internships bot
#

# Get environment name from command line argument, default to 'chatd'
ENV_NAME="${1:-chatd}"
ENV_DIR="/opt/$ENV_NAME"

# Validate environment name
if [[ ! "$ENV_NAME" =~ ^[a-z0-9][a-z0-9-]*[a-z0-9]$ ]] && [[ ! "$ENV_NAME" =~ ^[a-z0-9]$ ]]; then
    echo "❌ Invalid environment name: $ENV_NAME"
    echo "Environment name must:"
    echo "  - Start and end with alphanumeric characters"
    echo "  - Contain only lowercase letters, numbers, and hyphens"
    echo "  - Examples: chatd, thatd, chatd-dev, newgrad-roles"
    exit 1
fi

echo "Creating ChatD management scripts for environment: $ENV_NAME"
echo "Working directory: $ENV_DIR"
echo ""

# Detect docker-compose command (v2 plugin vs v1 standalone)
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
    echo "✅ Detected Docker Compose V2 (docker compose)"
else
    DOCKER_COMPOSE_CMD="docker-compose"
    echo "✅ Detected Docker Compose V1 (docker-compose)"
fi
echo ""

# Build script - Build Docker image only with smart commit-based detection
create_chatd_build() {
    cat > /usr/local/bin/${ENV_NAME}-build << EOF
#!/bin/bash
set -e

# Detect docker-compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# Show help if requested
if [[ "\$1" == "--help" || "\$1" == "-h" ]]; then
    echo "${ENV_NAME} Bot Build Script"
    echo "Usage: ${ENV_NAME}-build [BRANCH]"
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
WORK_DIR="${ENV_DIR}"

# Branch priority: command line arg -> environment variable -> default to main
BRANCH="\${1:-\${CHATD_BRANCH:-main}}"

echo "🔄 Building ${ENV_NAME} Internships Bot..."
echo "📍 Repository: ${REPO_URL}"
echo "🌿 Branch: ${BRANCH}"
echo "📁 Working directory: ${WORK_DIR}"

# Show branch source for clarity
if [[ -n "$1" ]]; then
    echo "   (specified via command line)"
elif [[ -n "$CHATD_BRANCH" ]]; then
    echo "   (from CHATD_BRANCH environment variable)"
else
    echo "   (default branch)"
fi

# Disk space monitoring logic
DISK_USAGE=$(df --output=pcent / | tail -1 | tr -dc '0-9')
AVAILABLE=$(df --output=avail / | tail -1)
if [ "$DISK_USAGE" -ge 90 ]; then
    echo "⚠️ Disk usage above 90%. Running emergency cleanup..."
    sudo chatd-prune
elif [ "$DISK_USAGE" -ge 80 ]; then
    echo "⚠️ Warning: Disk usage at ${DISK_USAGE}%. Consider manual cleanup."
fi
if [ "$AVAILABLE" -lt $((1024 * 1024)) ]; then
    echo "❌ Not enough disk space to build new images. Aborting."
    exit 1
fi

# Create or update working directory
if [[ -d "$WORK_DIR" ]]; then
    echo "📡 Updating existing repository..."
    cd "$WORK_DIR"
    
    # Preserve .env file during git operations
    if [[ -f ".env" ]]; then
        echo "💾 Preserving existing .env configuration"
    fi
    
    # Update to latest code
    git fetch origin
    git checkout "$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    echo "📡 Cloning repository to working directory..."
    mkdir -p "$(dirname "$WORK_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$WORK_DIR"
    cd "$WORK_DIR"
fi

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
\$DOCKER_COMPOSE_CMD build chatd-bot

# Tag the built image with commit hash and latest
BUILT_IMAGE_ID=$(docker images -q chatd_chatd-bot:latest)
if [[ -n "$BUILT_IMAGE_ID" ]]; then
    docker tag "$BUILT_IMAGE_ID" "${IMAGE_TAG}"
    docker tag "$BUILT_IMAGE_ID" "${LATEST_TAG}"
else
    echo "❌ Failed to find built image"
    exit 1
fi

# Also tag as latest
echo "🏷️  Tagging as latest..."
docker tag "${IMAGE_TAG}" "${LATEST_TAG}"

echo "✅ Bot image built successfully!"
echo "📦 Image: ${IMAGE_TAG}"
echo "ℹ️  Use 'chatd deploy' to restart with the new image."
EOF
    chmod +x /usr/local/bin/${ENV_NAME}-build
}

# Deploy script - Restart service with existing image
create_chatd_deploy() {
    cat > /usr/local/bin/${ENV_NAME}-deploy << EOF
#!/bin/bash
set -e

# Detect docker-compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

echo "🚀 Deploying ${ENV_NAME} Internships Bot..."

# Check if image exists
if ! docker image inspect chatd-internships:latest >/dev/null 2>&1; then
    echo "❌ Docker image 'chatd-internships:latest' not found!"
    echo "ℹ️  Run 'chatd build' first to create the image."
    exit 1
fi


# Disk space monitoring logic
DISK_USAGE=$(df --output=pcent / | tail -1 | tr -dc '0-9')
AVAILABLE=$(df --output=avail / | tail -1)
if [ "$DISK_USAGE" -ge 90 ]; then
    echo "⚠️ Disk usage above 90%. Running emergency cleanup..."
    sudo chatd-prune
elif [ "$DISK_USAGE" -ge 80 ]; then
    echo "⚠️ Warning: Disk usage at ${DISK_USAGE}%. Consider manual cleanup."
fi
if [ "$AVAILABLE" -lt $((1024 * 1024)) ]; then
    echo "❌ Not enough disk space to deploy new images. Aborting."
    exit 1
fi

# Deploy using docker-compose (which handles networking properly)
echo "🔄 Deploying bot with docker-compose..."

WORK_DIR="${ENV_DIR}"

# Check if working directory exists
if [[ ! -d "\$WORK_DIR" ]]; then
    echo "❌ Error: Working directory $WORK_DIR not found"
    echo "   Run 'chatd build' first to set up the working directory"
    exit 1
fi

# Change to working directory
cd "$WORK_DIR"

# Verify required files exist
if [[ ! -f "docker-compose.yml" ]]; then
    echo "❌ Error: docker-compose.yml not found in $WORK_DIR"
    echo "   Run 'chatd build' to update the working directory"
    exit 1
fi

if [[ ! -f ".env" ]]; then
    echo "⚠️  Warning: .env file not found in $WORK_DIR"
    echo "   Create .env file with your configuration before deployment"
    echo "   Example: cp examples/.env.example .env && nano .env"
    exit 1
fi

echo "🐳 Using docker-compose.yml in $WORK_DIR"

# Stop any existing containers
echo "🛑 Stopping existing containers..."
\$DOCKER_COMPOSE_CMD down --remove-orphans || echo "   (No containers were running)"

# Start services with docker-compose
echo "🚀 Starting services with docker-compose..."
if \$DOCKER_COMPOSE_CMD up -d; then
    echo "✅ Bot deployed successfully via docker-compose!"
    
    # Wait a moment for containers to start
    sleep 3
    
    # Show status
    echo ""
    echo "📊 Container Status:"
    \$DOCKER_COMPOSE_CMD ps
else
    echo "❌ Error: docker-compose deployment failed"
    echo "   Falling back to systemctl for compatibility..."
    if systemctl is-active --quiet ${ENV_NAME}; then
        echo "🔄 Restarting service with new image..."
        systemctl restart ${ENV_NAME}
        echo "✅ Bot deployed successfully!"
    else
        echo "🚀 Starting bot service..."
        systemctl start ${ENV_NAME}
        echo "✅ Bot started successfully!"
    fi
fi

# --- Docker Image Auto-Pruning ---
echo "🧹 Cleaning up old Docker images..."
RETENTION_COUNT=${CHATD_DOCKER_RETENTION:-3}

echo "📊 Retention policy: keeping $RETENTION_COUNT images (current + 2 rollback options)"

# Get all chatd-internships image tags sorted by creation date (newest first)
IMAGE_TAGS=$(docker images chatd-internships --format "{{.Tag}}" | grep -v latest)

# Remove images older than retention count
echo "$IMAGE_TAGS" | tail -n +$((RETENTION_COUNT + 1)) | while read tag; do
    if [[ -n "$tag" ]]; then
        echo "🗑️  Removing old image: chatd-internships:$tag"
        docker rmi "chatd-internships:$tag" 2>/dev/null || true
    fi
done

echo "✅ Cleanup complete. Retained $RETENTION_COUNT images."
EOF
    chmod +x /usr/local/bin/${ENV_NAME}-deploy
}

# Update script - Build and deploy with smart detection
create_chatd_update() {
    cat > /usr/local/bin/${ENV_NAME}-update << EOF
#!/bin/bash
set -e

# Detect docker-compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# Configuration
REPO_URL="https://github.com/builtbybob/chatd-internships.git"
WORK_DIR="${ENV_DIR}"

# Branch priority: command line arg -> environment variable -> default to main
BRANCH="\${1:-\${CHATD_BRANCH:-main}}"

echo "🔄 Updating ${ENV_NAME} Internships Bot (build + deploy)..."
echo "📍 Repository: ${REPO_URL}"
echo "🌿 Branch: ${BRANCH}"
echo "📁 Working directory: ${WORK_DIR}"

# Show branch source for clarity
if [[ -n "$1" ]]; then
    echo "   (specified via command line)"
elif [[ -n "$CHATD_BRANCH" ]]; then
    echo "   (from CHATD_BRANCH environment variable)"
else
    echo "   (default branch)"
fi

# Create or update working directory
if [[ -d "$WORK_DIR" ]]; then
    echo "📡 Updating existing repository..."
    cd "$WORK_DIR"
    
    # Preserve .env file during git operations
    if [[ -f ".env" ]]; then
        echo "💾 Preserving existing .env configuration"
    fi
    
    # Update to latest code
    git fetch origin
    git checkout "$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    echo "📡 Cloning repository to working directory..."
    mkdir -p "$(dirname "$WORK_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$WORK_DIR"
    cd "$WORK_DIR"
fi

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
    \$DOCKER_COMPOSE_CMD build chatd-bot
    
    # Tag the built image with commit hash and latest
    BUILT_IMAGE_ID=$(docker images -q chatd_chatd-bot:latest)
    if [[ -n "$BUILT_IMAGE_ID" ]]; then
        docker tag "$BUILT_IMAGE_ID" "${IMAGE_TAG}"
        docker tag "$BUILT_IMAGE_ID" "${LATEST_TAG}"
        echo "✅ Bot image built successfully!"
    else
        echo "❌ Failed to find built image"
        exit 1
    fi
fi

# Deploy using docker-compose (which handles networking properly)
echo "🔄 Deploying bot with docker-compose..."

# We're already in the working directory from the build step
# Verify required files exist
if [[ ! -f "docker-compose.yml" ]]; then
    echo "❌ Error: docker-compose.yml not found in working directory"
    echo "   This should not happen - check repository contents"
    exit 1
fi

if [[ ! -f ".env" ]]; then
    echo "⚠️  Warning: .env file not found"
    echo "   Create .env file with your configuration before deployment"
    echo "   Example: cp examples/.env.example .env && nano .env"
    exit 1
fi

echo "🐳 Using docker-compose.yml in $(pwd)"

# Stop any existing containers
echo "🛑 Stopping existing containers..."
\$DOCKER_COMPOSE_CMD down --remove-orphans || echo "   (No containers were running)"

# Start services with docker-compose
echo "� Starting services with docker-compose..."
if \$DOCKER_COMPOSE_CMD up -d; then
    echo "✅ Bot updated and deployed via docker-compose!"
    echo "📦 Running: ${IMAGE_TAG}"
    
    # Wait a moment for containers to start
    sleep 3
    
    # Show status
    echo ""
    echo "📊 Container Status:"
    \$DOCKER_COMPOSE_CMD ps
else
    echo "❌ Error: docker-compose deployment failed"
    echo "   Falling back to systemctl for compatibility..."
    if systemctl is-active --quiet ${ENV_NAME}; then
        echo "🔄 Restarting service..."
        systemctl restart ${ENV_NAME}
        echo "✅ Bot updated and deployed!"
        echo "📦 Running: ${IMAGE_TAG}"
    else
        echo "🚀 Starting bot service..."
        systemctl start ${ENV_NAME}
        echo "✅ Bot built and started!"
        echo "📦 Running: ${IMAGE_TAG}"
    fi
fi

# --- Docker Image Auto-Pruning ---
echo "🧹 Cleaning up old Docker images..."
RETENTION_COUNT=${CHATD_DOCKER_RETENTION:-3}

echo "📊 Retention policy: keeping $RETENTION_COUNT images (current + 2 rollback options)"

# Get all chatd-internships image tags sorted by creation date (newest first)
IMAGE_TAGS=$(docker images chatd-internships --format "{{.Tag}}" | grep -v latest)

# Remove images older than retention count
echo "$IMAGE_TAGS" | tail -n +$((RETENTION_COUNT + 1)) | while read tag; do
    if [[ -n "$tag" ]]; then
        echo "🗑️  Removing old image: chatd-internships:$tag"
        docker rmi "chatd-internships:$tag" 2>/dev/null || true
    fi
done

echo "✅ Cleanup complete. Retained $RETENTION_COUNT images."
EOF
    chmod +x /usr/local/bin/${ENV_NAME}-update
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
    cat > "/usr/local/bin/${ENV_NAME}-loglevel" << EOF
#!/bin/bash
# ${ENV_NAME} Bot - Dynamic Log Level Control
# Change log levels without restarting the bot

CONTAINER_NAME="${ENV_NAME}-bot"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^\${CONTAINER_NAME}\$"; then
    echo "❌ \${ENV_NAME} bot container is not running"
    echo "   Start it with: ${ENV_NAME} start"
    exit 1
fi

# Function to set log level
set_log_level() {
    local level="\$1"
    
    # Write level to temp file and signal the container
    echo "\${level}" | docker exec -i "\${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
    
    # Send SIGHUP signal to trigger level change (using docker kill instead of exec kill)
    docker kill --signal=HUP "\${CONTAINER_NAME}" > /dev/null
    
    echo "📝 Log level changed to: \${level}"
    echo "   View logs with: ${ENV_NAME} logs bot"
}

# Parse command line argument
case "\${1:-}" in
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
        echo "Usage: ${ENV_NAME}-loglevel <level>"
        echo ""
        echo "Available log levels:"
        echo "  debug    - Very verbose, shows all debug information"
        echo "  info     - Normal operations, startup/shutdown messages"
        echo "  warning  - Warnings and more severe messages only"
        echo "  error    - Error conditions and critical issues only"
        echo "  critical - Only critical system failures"
        echo ""
        echo "Current container status:"
        docker ps --format "  {{.Names}}: {{.Status}}" --filter name="\${CONTAINER_NAME}"
        exit 1
        ;;
    *)
        echo "❌ Invalid log level: \$1"
        echo "   Valid levels: debug, info, warning, error, critical"
        exit 1
        ;;
esac
EOF
    chmod +x "/usr/local/bin/${ENV_NAME}-loglevel"
}

# Logs script - View bot logs
create_chatd_logs() {
    cat > "/usr/local/bin/${ENV_NAME}-logs" << 'EOF'
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
            tail -f /opt/chatd/logs/chatd.log 2>/dev/null || echo "❌ No application logs found"
        else
            echo "📋 Last $LINES lines of application logs:"
            tail -n "$LINES" /opt/chatd/logs/chatd.log 2>/dev/null || echo "❌ No application logs found"
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
            journalctl -f -u ${ENV_NAME}
        else
            echo "⚙️  Last $LINES lines of systemd logs:"
            journalctl -n "$LINES" -u ${ENV_NAME}
        fi
        ;;
esac
EOF
    chmod +x "/usr/local/bin/${ENV_NAME}-logs"
}

# Backup script - Backup bot data
create_chatd_backup() {
    cat > "/usr/local/bin/${ENV_NAME}-backup" << 'EOF'
#!/bin/bash
set -e

# Create backup with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/chatd_backup_$TIMESTAMP.tar.gz"

echo "💾 Creating backup of ChatD bot data..."

# Create compressed backup
tar -czf "$BACKUP_FILE" \
    -C /opt/chatd data \
    -C /opt/chatd .env \
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
    chmod +x "/usr/local/bin/${ENV_NAME}-backup"
}

# Data inspection script
create_chatd_data() {
    cat > "/usr/local/bin/${ENV_NAME}-data" << 'EOF'
#!/bin/bash

echo "📊 ChatD Bot Data Status"
echo "========================"

# Bot Data Files
echo ""
echo "📁 Bot Data Files:"
if [[ -d "/opt/chatd/data" ]]; then
    ls -la /opt/chatd/data/ 2>/dev/null || echo "   (empty)"
else
    echo "   ❌ Data directory not found"
fi

# Repository Status
echo ""
echo "📚 Repository Status:"
if [[ -d "/opt/chatd/Summer2026-Internships" ]]; then
    cd /opt/chatd/Summer2026-Internships 2>/dev/null && {
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
systemctl status ${ENV_NAME} --no-pager -l || echo "   ❌ Service status unknown"

# Recent Log Summary
echo ""
echo "📋 Recent Activity:"
if [[ -f "/opt/chatd/logs/chatd.log" ]]; then
    echo "   Last 5 log entries:"
    tail -5 /opt/chatd/logs/chatd.log | sed 's/^/   /'
else
    echo "   ❌ No log file found"
fi

# Disk Usage
echo ""
echo "💾 Disk Usage:"
echo "   Data: $(du -sh /opt/chatd 2>/dev/null | cut -f1 || echo 'unknown')"
echo "   Logs: $(du -sh /opt/chatd/logs 2>/dev/null | cut -f1 || echo 'unknown')"
EOF
    chmod +x "/usr/local/bin/${ENV_NAME}-data"
}

# Control script - Start/stop/restart with shortcuts
create_chatd_control() {
    cat > /usr/local/bin/${ENV_NAME} << EOF
#!/bin/bash

# Detect docker-compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_usage() {
    echo "${ENV_NAME} Bot Control Script"
    echo "Usage: ${ENV_NAME} <command>"
    echo ""
    echo "Commands:"
    echo "  start      Start the bot service"
    echo "  stop       Stop the bot service"
    echo "  restart    Restart the bot service"
    echo "  status     Show service status"
    echo "  enable     Enable service to start on boot"
    echo "  disable    Disable service auto-start"
    echo "  logs [container]  Show logs (bot, postgres, or all)"
    echo "  loglevel <level>  Change bot log level (debug, info, warning, error, critical)"
    echo "  shell [container] Open bash shell in container (defaults to bot)"
    echo "  db [query]     Connect to PostgreSQL database (or run inline query)"
    echo "  pull       Pull latest Docker images"
    echo "  docker-update  Pull images, rebuild, and restart (docker-compose workflow)"
    echo "  docker-cleanup Clean up Docker resources (images, volumes)"
    echo "  data       Show data status (alias for ${ENV_NAME}-data)"
    echo "  backup     Create backup (alias for ${ENV_NAME}-backup)"
    echo "  build      Build Docker image (alias for chatd-build)"
    echo "  deploy     Deploy with existing image (alias for chatd-deploy)"
    echo "  update     Build and deploy together (alias for chatd-update)"
    echo "  version    Show version information (alias for chatd-version)"
    echo "  cleanup    Manual image cleanup (alias for chatd-cleanup)"
    echo "  images     List all ChatD images (alias for chatd-images)"
    echo "  prune      Aggressive cleanup (alias for chatd-prune)"
    echo "  disk       Show disk usage and image status (alias for chatd-disk)"
    echo ""
    echo "Docker Compose Commands:"
    echo "  compose-up     Start services with docker-compose"
    echo "  compose-down   Stop services with docker-compose"
    echo "  compose-ps     Show docker-compose service status"
    echo "  compose-logs   Show docker-compose logs"
    echo ""
    echo "Examples:"
    echo "  ${ENV_NAME} start           # Start the bot"
    echo "  ${ENV_NAME} build           # Build new image"
    echo "  ${ENV_NAME} build dev       # Build from specific branch"
    echo "  ${ENV_NAME} deploy          # Deploy with existing image"
    echo "  ${ENV_NAME} update          # Build and deploy together"
    echo "  ${ENV_NAME} version         # Show current version"
    echo "  ${ENV_NAME} logs            # Follow all logs"
    echo "  ${ENV_NAME} logs bot        # Follow bot logs only"
    echo "  ${ENV_NAME} logs postgres   # Follow database logs only"
    echo "  ${ENV_NAME} status          # Check if bot is running"
    echo "  ${ENV_NAME} shell           # Open shell in bot container"
    echo "  ${ENV_NAME} shell postgres  # Open shell in postgres container"
    echo "  ${ENV_NAME} db              # Interactive PostgreSQL session"
    echo "  ${ENV_NAME} db \"SELECT * FROM applicants LIMIT 5;\"  # Run inline query"
    echo "  ${ENV_NAME} pull            # Pull latest Docker images"
    echo "  ${ENV_NAME} docker-update   # Pull, rebuild, and restart"
    echo "  ${ENV_NAME} docker-cleanup  # Clean up Docker resources"
    echo "  ${ENV_NAME} cleanup --dry-run   # Preview images to be deleted"
    echo "  ${ENV_NAME} cleanup --count 5   # Keep 5 images"
    echo "  ${ENV_NAME} images              # List images with sizes"
    echo "  ${ENV_NAME} prune               # Keep only latest image"
    echo ""
    echo "Environment Variables:"
    echo "  CHATD_BRANCH          # Default branch for build/update commands"
    echo "                        # Example: export CHATD_BRANCH=dev"
    echo ""
    echo "Directory Structure:"
    echo "  ${ENV_DIR}/           # Working directory containing source code,"
    echo "                        # docker-compose.yml, and .env configuration"
    echo "  Run '${ENV_NAME} build' first to set up the working directory"
}

case "\$1" in
    start)
        echo -e "\${GREEN}🚀 Starting ${ENV_NAME} bot...\${NC}"
        sudo systemctl start ${ENV_NAME}
        ;;
    stop)
        echo -e "\${YELLOW}⏹️  Stopping ${ENV_NAME} bot...\${NC}"
        sudo systemctl stop ${ENV_NAME}
        ;;
    restart)
        echo -e "\${BLUE}🔄 Restarting ${ENV_NAME} bot...\${NC}"
        sudo systemctl restart ${ENV_NAME}
        ;;
    status)
        echo -e "\${BLUE}📊 ${ENV_NAME} Environment Status\${NC}"
        echo "=================================="
        echo ""
        echo -e "\${YELLOW}🔧 Systemd Service:\${NC}"
        sudo systemctl status ${ENV_NAME} --no-pager -l || true
        echo ""
        echo -e "\${YELLOW}🐳 Docker Containers:\${NC}"
        if [[ -d "${ENV_DIR}" && -f "${ENV_DIR}/docker-compose.yml" ]]; then
            sudo bash -c "cd ${ENV_DIR} && \$DOCKER_COMPOSE_CMD ps"
        else
            echo -e "   \${RED}❌ Working directory not found\${NC}"
        fi
        echo ""
        echo -e "\${YELLOW}💾 Database Status:\${NC}"
        if [[ -d "${ENV_DIR}" && -f "${ENV_DIR}/docker-compose.yml" ]]; then
            sudo bash -c "cd ${ENV_DIR} && \$DOCKER_COMPOSE_CMD exec -T ${ENV_NAME}-postgres pg_isready -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_}" 2>/dev/null && echo -e "   \${GREEN}✅ Database is ready\${NC}" || echo -e "   \${RED}❌ Database not accessible\${NC}"
        else
            echo -e "   \${RED}❌ Working directory not found\${NC}"
        fi
        ;;
    enable)
        echo -e "\${GREEN}✅ Enabling ${ENV_NAME} bot auto-start...\${NC}"
        sudo systemctl enable ${ENV_NAME}
        ;;
    disable)
        echo -e "\${YELLOW}❌ Disabling ${ENV_NAME} bot auto-start...\${NC}"
        sudo systemctl disable ${ENV_NAME}
        ;;
    logs)
        CONTAINER="\${2:-}"
        if [[ -n "\$CONTAINER" ]]; then
            echo -e "\${BLUE}📋 Logs for ${ENV_NAME}-\$CONTAINER\${NC}"
            cd "${ENV_DIR}" && \$DOCKER_COMPOSE_CMD logs -f "${ENV_NAME}-\${CONTAINER}"
        else
            echo -e "\${BLUE}📋 All logs for ${ENV_NAME}\${NC}"
            cd "${ENV_DIR}" && \$DOCKER_COMPOSE_CMD logs -f
        fi
        ;;
    loglevel)
        LEVEL="\${2:-}"
        CONTAINER_NAME="${ENV_NAME}-bot"
        
        # Check if container is running
        if ! docker ps --format '{{.Names}}' | grep -q "^\${CONTAINER_NAME}\$"; then
            echo -e "\${RED}❌ ${ENV_NAME} bot container is not running\${NC}"
            echo "   Start it with: ${ENV_NAME} start"
            exit 1
        fi
        
        case "\${LEVEL}" in
            debug|DEBUG)
                echo "DEBUG" | docker exec -i "\${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
                docker kill --signal=HUP "\${CONTAINER_NAME}" > /dev/null
                echo -e "\${GREEN}📝 Log level changed to: DEBUG\${NC}"
                echo -e "\${BLUE}   🔍 Debug logging enabled - very verbose output\${NC}"
                echo -e "\${BLUE}   View logs with: ${ENV_NAME} logs bot\${NC}"
                ;;
            info|INFO)
                echo "INFO" | docker exec -i "\${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
                docker kill --signal=HUP "\${CONTAINER_NAME}" > /dev/null
                echo -e "\${GREEN}📝 Log level changed to: INFO\${NC}"
                echo -e "\${BLUE}   ℹ️  Info logging enabled - normal operational messages\${NC}"
                ;;
            warning|WARNING|warn|WARN)
                echo "WARNING" | docker exec -i "\${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
                docker kill --signal=HUP "\${CONTAINER_NAME}" > /dev/null
                echo -e "\${GREEN}📝 Log level changed to: WARNING\${NC}"
                echo -e "\${BLUE}   ⚠️  Warning logging enabled - warnings and errors only\${NC}"
                ;;
            error|ERROR)
                echo "ERROR" | docker exec -i "\${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
                docker kill --signal=HUP "\${CONTAINER_NAME}" > /dev/null
                echo -e "\${GREEN}📝 Log level changed to: ERROR\${NC}"
                echo -e "\${BLUE}   ❌ Error logging enabled - errors and critical only\${NC}"
                ;;
            critical|CRITICAL|crit|CRIT)
                echo "CRITICAL" | docker exec -i "\${CONTAINER_NAME}" tee /tmp/chatd_loglevel > /dev/null
                docker kill --signal=HUP "\${CONTAINER_NAME}" > /dev/null
                echo -e "\${GREEN}📝 Log level changed to: CRITICAL\${NC}"
                echo -e "\${BLUE}   🚨 Critical logging enabled - critical errors only\${NC}"
                ;;
            "")
                echo "Usage: ${ENV_NAME} loglevel <level>"
                echo ""
                echo "Available log levels:"
                echo "  debug    - Very verbose, shows all debug information"
                echo "  info     - Normal operations, startup/shutdown messages"
                echo "  warning  - Warnings and more severe messages only"
                echo "  error    - Error conditions and critical issues only"
                echo "  critical - Only critical system failures"
                echo ""
                echo "Current container status:"
                docker ps --format "  {{.Names}}: {{.Status}}" --filter name="\${CONTAINER_NAME}"
                exit 1
                ;;
            *)
                echo -e "\${RED}❌ Invalid log level: \$LEVEL\${NC}"
                echo "   Valid levels: debug, info, warning, error, critical"
                exit 1
                ;;
        esac
        ;;
    shell)
        CONTAINER="\${2:-bot}"
        echo -e "\${BLUE}🐚 Opening shell in ${ENV_NAME}-\$CONTAINER...\${NC}"
        cd "${ENV_DIR}" && sudo -E \$DOCKER_COMPOSE_CMD exec "${ENV_NAME}-\${CONTAINER}" /bin/bash
        ;;
    db)
        QUERY="\${2:-}"
        if [[ -n "\$QUERY" ]]; then
            # Inline query mode - use -T flag for non-interactive
            echo -e "\${BLUE}🗄️  Running query on ${ENV_NAME} database...\${NC}"
            cd "${ENV_DIR}" && sudo -E \$DOCKER_COMPOSE_CMD exec -T ${ENV_NAME}-postgres psql -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_} -c "\$QUERY"
        else
            # Interactive mode - open psql session
            echo -e "\${BLUE}🗄️  Connecting to ${ENV_NAME} database...\${NC}"
            cd "${ENV_DIR}" && sudo -E \$DOCKER_COMPOSE_CMD exec ${ENV_NAME}-postgres psql -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_}
        fi
        ;;
    pull)
        echo -e "\${BLUE}📥 Pulling latest Docker images for ${ENV_NAME}...\${NC}"
        if [[ -d "${ENV_DIR}" && -f "${ENV_DIR}/docker-compose.yml" ]]; then
            cd "${ENV_DIR}" && sudo -E \$DOCKER_COMPOSE_CMD pull
            echo -e "\${GREEN}✅ Images pulled successfully\${NC}"
        else
            echo -e "\${RED}❌ Working directory not found\${NC}"
            exit 1
        fi
        ;;
    docker-update)
        echo -e "\${BLUE}🔄 Updating ${ENV_NAME} environment (pull + rebuild + restart)...\${NC}"
        if [[ -d "${ENV_DIR}" && -f "${ENV_DIR}/docker-compose.yml" ]]; then
            cd "${ENV_DIR}"
            echo -e "\${BLUE}📥 Pulling latest images...\${NC}"
            sudo -E \$DOCKER_COMPOSE_CMD pull
            echo -e "\${BLUE}🔨 Rebuilding containers...\${NC}"
            sudo -E \$DOCKER_COMPOSE_CMD build
            echo -e "\${BLUE}🔄 Restarting services...\${NC}"
            sudo -E \$DOCKER_COMPOSE_CMD up -d
            echo -e "\${GREEN}✅ ${ENV_NAME} environment updated successfully\${NC}"
        else
            echo -e "\${RED}❌ Working directory not found\${NC}"
            exit 1
        fi
        ;;
    docker-cleanup)
        echo -e "\${YELLOW}🧹 Cleaning up ${ENV_NAME} Docker resources...\${NC}"
        if [[ -d "${ENV_DIR}" && -f "${ENV_DIR}/docker-compose.yml" ]]; then
            cd "${ENV_DIR}"
            echo -e "\${YELLOW}Stopping containers...\${NC}"
            sudo -E \$DOCKER_COMPOSE_CMD down
            echo -e "\${YELLOW}Removing unused images...\${NC}"
            docker image prune -f
            echo -e "\${YELLOW}Removing unused volumes (excluding data)...\${NC}"
            docker volume prune -f
            echo -e "\${GREEN}✅ Cleanup complete\${NC}"
        else
            echo -e "\${RED}❌ Working directory not found\${NC}"
            exit 1
        fi
        ;;
    data)
        ${ENV_NAME}-data
        ;;
    backup)
        ${ENV_NAME}-backup
        ;;
    build)
        shift
        chatd-build "\$@"
        ;;
    deploy)
        chatd-deploy
        ;;
    update)
        shift
        chatd-update "\$@"
        ;;
    version)
        shift
        chatd-version "\$@"
        ;;
    cleanup)
        shift
        chatd-cleanup "\$@"
        ;;
    images)
        chatd-images
        ;;
    prune)
        chatd-prune
        ;;
    disk)
        shift
        chatd-disk "\$@"
        ;;
    compose-up)
        echo "🐳 Starting services with docker-compose..."
        
        WORK_DIR="${ENV_DIR}"
        if [[ -d "\$WORK_DIR" && -f "\$WORK_DIR/docker-compose.yml" ]]; then
            cd "\$WORK_DIR"
            echo "🐳 Using docker-compose.yml in \$WORK_DIR"
            \$DOCKER_COMPOSE_CMD up -d
            echo "📊 Container Status:"
            \$DOCKER_COMPOSE_CMD ps
        else
            echo "❌ Working directory \$WORK_DIR not found or missing docker-compose.yml"
            echo "   Run '${ENV_NAME} build' first to set up the working directory"
        fi
        ;;
    compose-down)
        echo "🛑 Stopping services with docker-compose..."
        
        WORK_DIR="${ENV_DIR}"
        if [[ -d "\$WORK_DIR" && -f "\$WORK_DIR/docker-compose.yml" ]]; then
            cd "\$WORK_DIR"
            \$DOCKER_COMPOSE_CMD down --remove-orphans
        else
            echo "❌ Working directory \$WORK_DIR not found or missing docker-compose.yml"
        fi
        ;;
    compose-ps)
        echo "📊 Docker Compose Service Status:"
        
        WORK_DIR="${ENV_DIR}"
        if [[ -d "\$WORK_DIR" && -f "\$WORK_DIR/docker-compose.yml" ]]; then
            cd "\$WORK_DIR"
            \$DOCKER_COMPOSE_CMD ps
        else
            echo "❌ Working directory \$WORK_DIR not found or missing docker-compose.yml"
        fi
        ;;
    compose-logs)
        echo "📋 Docker Compose Logs:"
        
        WORK_DIR="${ENV_DIR}"
        if [[ -d "\$WORK_DIR" && -f "\$WORK_DIR/docker-compose.yml" ]]; then
            cd "\$WORK_DIR"
            shift
            \$DOCKER_COMPOSE_CMD logs "\$@"
        else
            echo "❌ Working directory \$WORK_DIR not found or missing docker-compose.yml"
        fi
        ;;
    ""|help|-h|--help)
        show_usage
        ;;
    *)
        echo "❌ Unknown command: \$1"
        echo ""
        show_usage
        exit 1
        ;;
esac
EOF
    chmod +x /usr/local/bin/${ENV_NAME}
}

# Main execution
echo "Creating ChatD management scripts..."

create_chatd_build
echo "✅ Created chatd-build (shared across all environments)"

create_chatd_deploy
echo "✅ Created chatd-deploy (shared across all environments)"

create_chatd_update
echo "✅ Created chatd-update (shared across all environments)"

create_chatd_version
echo "✅ Created chatd-version (shared across all environments)"

create_chatd_loglevel
echo "✅ Created ${ENV_NAME}-loglevel"

create_chatd_logs
echo "✅ Created ${ENV_NAME}-logs" 

create_chatd_backup
echo "✅ Created ${ENV_NAME}-backup"

create_chatd_data
echo "✅ Created ${ENV_NAME}-data"

create_chatd_control
echo "✅ Created ${ENV_NAME} (main control script)"

create_chatd_cleanup
echo "✅ Created chatd-cleanup (shared across all environments)"

create_chatd_images
echo "✅ Created chatd-images (shared across all environments)"

create_chatd_prune
echo "✅ Created chatd-prune (shared across all environments)"

create_chatd_disk
echo "✅ Created chatd-disk (shared across all environments)"

echo ""
echo "🎉 All management scripts created successfully for environment: $ENV_NAME!"
echo ""
echo "📋 Directory Structure Information:"
echo "   Working directory: $ENV_DIR/"
echo "   Run '${ENV_NAME} build' to set up the working directory with latest source"
echo "   The .env file should be placed in $ENV_DIR/ alongside docker-compose.yml"
echo ""
echo "Available commands:"
echo "  ${ENV_NAME} start/stop/restart - Control the bot"
echo "  ${ENV_NAME} status            - Show service status"
echo "  ${ENV_NAME} enable/disable    - Enable/disable auto-start on boot"
echo "  ${ENV_NAME} logs [-f|-n N|--docker|--system] - View logs"
echo "  ${ENV_NAME} data              - Check bot data status"
echo "  ${ENV_NAME} backup            - Create data backup"
echo "  ${ENV_NAME} build [BRANCH]    - Build Docker image with smart detection"
echo "  ${ENV_NAME} deploy            - Deploy with existing image"
echo "  ${ENV_NAME} update [BRANCH]   - Build and deploy together"
echo "  ${ENV_NAME} version           - Show version and manage images"
echo "  ${ENV_NAME} cleanup [--count N|--dry-run] - Manual image cleanup"
echo "  ${ENV_NAME} images            - List all ChatD images with sizes"
echo "  ${ENV_NAME} prune             - Aggressive cleanup (keep only latest)"
echo "  ${ENV_NAME} disk [--metrics]  - Show disk usage and image status"
echo "  ${ENV_NAME}-loglevel <level>  - Change log level without restart"
