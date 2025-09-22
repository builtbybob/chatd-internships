#!/bin/bash
#
# ChatD System Backup Script
# Creates a complete backup of the ChatD bot system for migration
#

set -e

# Allow custom backup location via environment variable or parameter
BACKUP_BASE_DIR="${1:-${CHATD_BACKUP_DIR:-/home/$USER}}"
BACKUP_DIR="${BACKUP_BASE_DIR}/chatd-migration-backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="chatd_backup_${TIMESTAMP}"

echo "🔄 ChatD System Backup Starting..."
echo "Backup location: ${BACKUP_DIR}/${BACKUP_NAME}"

# Check available space
echo ""
echo "💾 Checking available space..."
AVAILABLE_KB=$(df "${BACKUP_BASE_DIR}" | awk 'NR==2 {print $4}')
AVAILABLE_MB=$((AVAILABLE_KB / 1024))
echo "Available space: ${AVAILABLE_MB}MB"

# Estimate backup size
echo "📏 Estimating backup size..."
CONFIG_SIZE=$(sudo du -s /etc/chatd 2>/dev/null | awk '{print $1}' || echo "0")
DATA_SIZE=$(sudo du -s /var/lib/chatd 2>/dev/null | awk '{print $1}' || echo "0")
SSH_SIZE=$(du -s "$HOME/.ssh" 2>/dev/null | awk '{print $1}' || echo "0")
DOCKER_SIZE_MB=$(sudo docker images chatd-internships --format "{{.Size}}" | head -1 | sed 's/MB//' || echo "400")
DOCKER_SIZE_KB=$((DOCKER_SIZE_MB * 1024))

TOTAL_ESTIMATED_KB=$((CONFIG_SIZE + DATA_SIZE + SSH_SIZE + DOCKER_SIZE_KB))
TOTAL_ESTIMATED_MB=$((TOTAL_ESTIMATED_KB / 1024))

echo "Estimated backup size: ${TOTAL_ESTIMATED_MB}MB"

if [ $AVAILABLE_MB -lt $((TOTAL_ESTIMATED_MB + 100)) ]; then
    echo ""
    echo "⚠️  WARNING: Insufficient space!"
    echo "   Available: ${AVAILABLE_MB}MB"
    echo "   Required:  ~${TOTAL_ESTIMATED_MB}MB"
    echo ""
    echo "Options:"
    echo "1. Use external drive: ./backup-system.sh /media/usb"
    echo "2. Use home directory: ./backup-system.sh /home/$USER"
    echo "3. Skip Docker images (add --no-docker flag)"
    echo "4. Free up space first"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Backup cancelled."
        exit 1
    fi
fi

# Create backup directory
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"
cd "${BACKUP_DIR}/${BACKUP_NAME}"

echo ""
echo "📁 Backing up configuration files..."
# Backup ChatD configuration
if [ -d "/etc/chatd" ]; then
    sudo cp -r /etc/chatd/ ./etc_chatd/
    echo "✅ ChatD configuration backed up"
else
    echo "⚠️  /etc/chatd not found - skipping"
fi

echo ""
echo "💾 Backing up application data..."
# Backup ChatD data
if [ -d "/var/lib/chatd" ]; then
    sudo cp -r /var/lib/chatd/ ./var_lib_chatd/
    echo "✅ ChatD data backed up"
else
    echo "⚠️  /var/lib/chatd not found - skipping"
fi

echo ""
echo "🔑 Backing up SSH configuration..."
# Backup SSH keys and config
if [ -d "$HOME/.ssh" ]; then
    cp -r "$HOME/.ssh/" ./ssh_config/
    echo "✅ SSH configuration backed up"
else
    echo "⚠️  SSH directory not found - skipping"
fi

echo ""
echo "🐳 Backing up Docker images..."
# Backup Docker images
if command -v docker &> /dev/null; then
    if docker images chatd-internships --format "{{.Repository}}" | grep -q chatd-internships; then
        docker save chatd-internships:latest > chatd-image.tar
        echo "✅ ChatD Docker image backed up"
        
        # Also save any other tagged versions
        docker images chatd-internships --format "{{.Repository}}:{{.Tag}}" | while read image; do
            if [[ "$image" != "chatd-internships:latest" ]]; then
                filename=$(echo "$image" | tr ':/' '_')
                docker save "$image" > "${filename}.tar"
                echo "✅ Docker image ${image} backed up"
            fi
        done
    else
        echo "⚠️  No ChatD Docker images found"
    fi
else
    echo "⚠️  Docker not available - skipping image backup"
fi

echo ""
echo "📋 Creating system information..."
# System information
cat > system_info.txt << EOF
ChatD System Backup Information
================================
Backup Date: $(date)
Hostname: $(hostname)
OS Version: $(cat /etc/os-release | grep PRETTY_NAME)
Kernel: $(uname -r)
Architecture: $(uname -m)
Disk Usage: $(df -h /)
Docker Version: $(docker --version 2>/dev/null || echo "Not installed")

ChatD Service Status:
$(systemctl status chatd-internships 2>/dev/null || echo "Service not found")

Docker Images:
$(docker images 2>/dev/null || echo "Docker not available")

Environment Variables (sanitized):
$(env | grep -E '^(PATH|HOME|USER|SHELL)=' | sort)
EOF

echo "✅ System information saved"

echo ""
echo "📦 Creating installation script..."
# Create installation script for new system
cat > install-on-new-system.sh << 'EOF'
#!/bin/bash
#
# ChatD System Restore Script
# Restores ChatD system from backup on new installation
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 ChatD System Restore Starting..."
echo "Restoring from: ${SCRIPT_DIR}"

# Check if running as regular user
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run this script as a regular user (not root)"
    echo "   The script will use sudo when needed"
    exit 1
fi

echo ""
echo "📋 Checking prerequisites..."
# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   sudo apt update && sudo apt install -y docker.io"
    echo "   sudo usermod -aG docker $USER"
    echo "   Then logout and login again"
    exit 1
fi

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo "❌ User is not in docker group. Please run:"
    echo "   sudo usermod -aG docker $USER"
    echo "   Then logout and login again"
    exit 1
fi

echo ""
echo "📁 Restoring configuration files..."
# Restore ChatD configuration
if [ -d "${SCRIPT_DIR}/etc_chatd" ]; then
    sudo mkdir -p /etc/chatd
    sudo cp -r "${SCRIPT_DIR}/etc_chatd/"* /etc/chatd/
    sudo chown -R root:root /etc/chatd
    sudo chmod 600 /etc/chatd/.env
    echo "✅ ChatD configuration restored"
fi

echo ""
echo "💾 Restoring application data..."
# Restore ChatD data
if [ -d "${SCRIPT_DIR}/var_lib_chatd" ]; then
    sudo mkdir -p /var/lib/chatd
    sudo cp -r "${SCRIPT_DIR}/var_lib_chatd/"* /var/lib/chatd/
    sudo chown -R 1000:1000 /var/lib/chatd
    echo "✅ ChatD data restored"
fi

echo ""
echo "🔑 Restoring SSH configuration..."
# Restore SSH configuration
if [ -d "${SCRIPT_DIR}/ssh_config" ]; then
    mkdir -p "$HOME/.ssh"
    cp -r "${SCRIPT_DIR}/ssh_config/"* "$HOME/.ssh/"
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME/.ssh/"*
    chmod 644 "$HOME/.ssh/"*.pub 2>/dev/null || true
    echo "✅ SSH configuration restored"
fi

echo ""
echo "🐳 Restoring Docker images..."
# Restore Docker images
for tar_file in "${SCRIPT_DIR}"/*.tar; do
    if [ -f "$tar_file" ]; then
        echo "Loading $(basename "$tar_file")..."
        docker load < "$tar_file"
        echo "✅ Loaded $(basename "$tar_file")"
    fi
done

echo ""
echo "📥 Checking for ChatD repository..."
# Check if ChatD repository exists
if [ ! -d "/home/$USER/dev/chatd-internships" ]; then
    echo "📥 Cloning ChatD repository..."
    mkdir -p "/home/$USER/dev"
    cd "/home/$USER/dev"
    git clone https://github.com/builtbybob/chatd-internships.git
    cd chatd-internships
else
    echo "📁 ChatD repository found, updating..."
    cd "/home/$USER/dev/chatd-internships"
    git pull
fi

echo ""
echo "🔧 Installing management scripts..."
# Install management scripts
sudo ./scripts/create-management-scripts.sh

echo ""
echo "⚙️  Setting up systemd service..."
# Enable and start service
sudo systemctl enable chatd-internships 2>/dev/null || echo "⚠️  Service file might need manual setup"
sudo systemctl daemon-reload

echo ""
echo "🎉 Restore Complete!"
echo ""
echo "Next steps:"
echo "1. Verify configuration: sudo nano /etc/chatd/.env"
echo "2. Start the service: sudo systemctl start chatd-internships"
echo "3. Check status: sudo chatd status"
echo "4. View logs: sudo chatd-logs -f"
echo "5. Test log levels: sudo chatd-loglevel debug"
echo ""
echo "If you encounter any issues, check the troubleshooting section in README.md"
EOF

chmod +x install-on-new-system.sh
echo "✅ Installation script created"

echo ""
echo "🗜️  Compressing backup..."
cd "${BACKUP_DIR}"
tar czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}/"
BACKUP_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)

echo ""
echo "🎉 Backup Complete!"
echo ""
echo "📁 Backup Location: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo "📏 Backup Size: ${BACKUP_SIZE}"
echo ""
echo "To transfer to new system:"
echo "1. Copy the backup file to your new system"
echo "2. Extract: tar xzf ${BACKUP_NAME}.tar.gz"
echo "3. Run: cd ${BACKUP_NAME} && ./install-on-new-system.sh"
echo ""
echo "Alternative transfer methods:"
echo "• USB drive: cp ${BACKUP_NAME}.tar.gz /media/usb/"
echo "• SCP: scp ${BACKUP_NAME}.tar.gz user@new-pi:~/"
echo "• Network share: Upload to cloud storage and download on new system"
