#!/bin/bash
#
# ChatD Bot Management Scripts
# These scripts help manage the dockerized ChatD Internships bot
#

# Build script - Update and rebuild the bot
create_chatd_build() {
    cat > /usr/local/bin/chatd-build << 'EOF'
#!/bin/bash
set -e

echo "🔄 Updating ChatD Internships Bot..."

# Navigate to source directory
cd /home/apathy/dev/chatd-internships

# Pull latest changes
echo "📡 Pulling latest changes from git..."
git pull

# Build new docker image
echo "🐳 Building Docker image..."
docker build -t chatd-internships:latest .

# Restart the service if it's running
if systemctl is-active --quiet chatd-internships; then
    echo "🔄 Restarting service..."
    systemctl restart chatd-internships
    echo "✅ Bot updated and restarted!"
else
    echo "ℹ️  Bot updated! Use 'sudo systemctl start chatd-internships' to start it."
fi
EOF
    chmod +x /usr/local/bin/chatd-build
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
    echo "  build      Update and rebuild (alias for chatd-build)"
    echo ""
    echo "Examples:"
    echo "  chatd start           # Start the bot"
    echo "  chatd logs -f         # Follow logs in real-time"
    echo "  chatd status          # Check if bot is running"
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
echo "  chatd-build             - Update and rebuild bot"
