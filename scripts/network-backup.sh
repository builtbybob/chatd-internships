#!/bin/bash
#
# Network Backup Script
# Backup ChatD system directly to another computer
#

set -e

echo "🌐 ChatD Network Backup Script"
echo ""

# Get backup destination
read -p "Enter destination (user@host:/path): " DEST
if [ -z "$DEST" ]; then
    echo "❌ Destination required!"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="chatd_backup_${TIMESTAMP}"

echo ""
echo "📡 Backing up to: ${DEST}/${BACKUP_NAME}"

# Test connection
echo "🔌 Testing connection..."
ssh $(echo "$DEST" | cut -d: -f1) "echo 'Connection OK'"

echo ""
echo "🚀 Starting backup..."

# Create remote directory
ssh $(echo "$DEST" | cut -d: -f1) "mkdir -p $(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}"

# Backup configurations
echo "📁 Backing up configurations..."
sudo tar czf - /etc/chatd/ | ssh $(echo "$DEST" | cut -d: -f1) "cat > $(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}/config.tar.gz"

# Backup data
echo "💾 Backing up data..."
sudo tar czf - /var/lib/chatd/ | ssh $(echo "$DEST" | cut -d: -f1) "cat > $(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}/data.tar.gz"

# Backup SSH keys
echo "🔑 Backing up SSH keys..."
tar czf - "$HOME/.ssh/" | ssh $(echo "$DEST" | cut -d: -f1) "cat > $(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}/ssh.tar.gz"

# Export Docker image
echo "🐳 Backing up Docker image..."
sudo docker save chatd-internships | gzip | ssh $(echo "$DEST" | cut -d: -f1) "cat > $(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}/docker-image.tar.gz"

# Create restore script
echo "📋 Creating restore script..."
cat > "/tmp/restore.sh" << 'EOF'
#!/bin/bash
set -e
BACKUP_DIR="$(dirname "$0")"
echo "🔄 Restoring ChatD system..."

# Restore configs
sudo tar xzf "${BACKUP_DIR}/config.tar.gz" -C /

# Restore data
sudo mkdir -p /var/lib/chatd
sudo tar xzf "${BACKUP_DIR}/data.tar.gz" -C /

# Restore SSH
tar xzf "${BACKUP_DIR}/ssh.tar.gz" -C "$HOME/"

# Load Docker image
docker load < "${BACKUP_DIR}/docker-image.tar.gz"

echo "✅ Restore completed!"
echo "Run: sudo systemctl restart chatd"
EOF

scp /tmp/restore.sh $(echo "$DEST" | cut -d: -f1):$(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}/
ssh $(echo "$DEST" | cut -d: -f1) "chmod +x $(echo "$DEST" | cut -d: -f2)/${BACKUP_NAME}/restore.sh"

echo ""
echo "✅ Network backup completed!"
echo ""
echo "Backup location: ${DEST}/${BACKUP_NAME}"
echo "To restore: run ./restore.sh in the backup directory"
