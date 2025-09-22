#!/bin/bash
#
# ChatD System Verification Script
# Verifies that ChatD system is properly installed and configured
#

set -e

echo "🔍 ChatD System Verification"
echo "============================="
echo ""

ISSUES=0

# Function to report status
check_status() {
    local description="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "Checking $description... "
    if eval "$command" &>/dev/null; then
        echo "✅ OK"
    else
        echo "❌ FAILED"
        if [ -n "$expected" ]; then
            echo "   Expected: $expected"
        fi
        ISSUES=$((ISSUES + 1))
    fi
}

# System checks
echo "🖥️  System Checks:"
check_status "Docker installation" "command -v docker"
check_status "Docker service" "systemctl is-active docker"
check_status "User in docker group" "groups | grep -q docker"
check_status "Git installation" "command -v git"

echo ""
echo "📁 File System Checks:"
check_status "ChatD configuration directory" "[ -d /etc/chatd ]"
check_status "ChatD environment file" "[ -f /etc/chatd/.env ]"
check_status "ChatD data directory" "[ -d /var/lib/chatd ]"
check_status "ChatD repository" "[ -d /home/$USER/dev/chatd-internships ]"

echo ""
echo "🐳 Docker Checks:"
check_status "ChatD Docker image" "docker images | grep -q chatd-internships"
check_status "ChatD container running" "docker ps | grep -q chatd-bot"

echo ""
echo "⚙️  Service Checks:"
check_status "ChatD systemd service exists" "systemctl list-unit-files | grep -q chatd-internships"
check_status "ChatD service enabled" "systemctl is-enabled chatd-internships"
check_status "ChatD service active" "systemctl is-active chatd-internships"

echo ""
echo "🔧 Management Script Checks:"
check_status "chatd command available" "command -v chatd"
check_status "chatd-logs command available" "command -v chatd-logs"
check_status "chatd-loglevel command available" "command -v chatd-loglevel"
check_status "chatd-build command available" "command -v chatd-build"

echo ""
echo "🔐 Permission Checks:"
check_status "ChatD config permissions" "[ '$(stat -c %a /etc/chatd/.env 2>/dev/null)' = '600' ]"
check_status "ChatD data ownership" "[ '$(stat -c %U /var/lib/chatd 2>/dev/null)' = 'apathy' ] || [ '$(stat -c %u /var/lib/chatd 2>/dev/null)' = '1000' ]"

echo ""
echo "💾 Disk Space Check:"
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "Disk usage: ✅ ${DISK_USAGE}% (healthy)"
elif [ "$DISK_USAGE" -lt 90 ]; then
    echo "Disk usage: ⚠️  ${DISK_USAGE}% (monitor closely)"
else
    echo "Disk usage: ❌ ${DISK_USAGE}% (critical - clean up needed)"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "🌐 Network Check:"
if ping -c 1 github.com &>/dev/null; then
    echo "Internet connectivity: ✅ OK"
else
    echo "Internet connectivity: ❌ FAILED"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "📊 Configuration Check:"
if [ -f /etc/chatd/.env ]; then
    echo "Environment variables:"
    while IFS= read -r line; do
        if [[ $line =~ ^[A-Z_]+=.+ ]]; then
            var_name=$(echo "$line" | cut -d'=' -f1)
            if [[ $var_name == *"TOKEN"* ]] || [[ $var_name == *"SECRET"* ]]; then
                echo "  $var_name=***HIDDEN***"
            else
                echo "  $line"
            fi
        fi
    done < /etc/chatd/.env
else
    echo "❌ No environment file found"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "🔨 Quick Tests:"
if command -v chatd &>/dev/null; then
    echo -n "Testing chatd status command... "
    if sudo chatd status &>/dev/null; then
        echo "✅ OK"
    else
        echo "❌ FAILED"
        ISSUES=$((ISSUES + 1))
    fi
    
    echo -n "Testing chatd-loglevel command... "
    if sudo chatd-loglevel info &>/dev/null; then
        echo "✅ OK"
    else
        echo "❌ FAILED"
        ISSUES=$((ISSUES + 1))
    fi
fi

echo ""
echo "=============================="
if [ $ISSUES -eq 0 ]; then
    echo "🎉 All checks passed! ChatD system is healthy."
    echo ""
    echo "Useful commands:"
    echo "  sudo chatd status           - Check service status"
    echo "  sudo chatd-logs -f          - Follow logs"
    echo "  sudo chatd-loglevel debug   - Enable debug logging"
    echo "  sudo chatd-build            - Rebuild Docker image"
else
    echo "⚠️  Found $ISSUES issue(s) that need attention."
    echo ""
    echo "Common fixes:"
    echo "  sudo systemctl start chatd-internships  - Start service"
    echo "  sudo ./scripts/create-management-scripts.sh  - Reinstall scripts"
    echo "  sudo chown -R 1000:1000 /var/lib/chatd/  - Fix permissions"
    echo "  sudo chmod 600 /etc/chatd/.env  - Fix config permissions"
fi

echo ""
echo "For detailed logs: sudo chatd-logs"
echo "For troubleshooting: See README.md server setup guide"
