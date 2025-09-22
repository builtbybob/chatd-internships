#!/bin/bash
#
# Direct Disk Clone Script
# Clone the entire microSD card to a new larger card
# Run this from a separate computer with both cards connected
#

set -e

echo "🔄 ChatD Disk Clone Script"
echo ""
echo "⚠️  WARNING: This will completely overwrite the target disk!"
echo ""

# Detect source disk
echo "📀 Available disks:"
lsblk -d -o NAME,SIZE,TYPE | grep disk

echo ""
read -p "Enter source disk (e.g., sdb): " SOURCE_DISK
read -p "Enter target disk (e.g., sdc): " TARGET_DISK

SOURCE_DEV="/dev/${SOURCE_DISK}"
TARGET_DEV="/dev/${TARGET_DISK}"

echo ""
echo "Source: ${SOURCE_DEV}"
echo "Target: ${TARGET_DEV}"

# Verify devices exist
if [ ! -b "${SOURCE_DEV}" ]; then
    echo "❌ Source disk ${SOURCE_DEV} not found!"
    exit 1
fi

if [ ! -b "${TARGET_DEV}" ]; then
    echo "❌ Target disk ${TARGET_DEV} not found!"
    exit 1
fi

# Show disk info
echo ""
echo "📊 Disk Information:"
echo "Source:"
lsblk "${SOURCE_DEV}"
echo ""
echo "Target:"
lsblk "${TARGET_DEV}"

echo ""
echo "⚠️  FINAL WARNING: This will erase ALL data on ${TARGET_DEV}!"
read -p "Type 'CLONE' to continue: " CONFIRM

if [ "$CONFIRM" != "CLONE" ]; then
    echo "Operation cancelled."
    exit 1
fi

echo ""
echo "🚀 Starting clone operation..."
echo "This may take 10-30 minutes depending on card size."

# Clone the disk
sudo dd if="${SOURCE_DEV}" of="${TARGET_DEV}" bs=4M status=progress

echo ""
echo "🔄 Syncing data..."
sudo sync

echo ""
echo "✅ Clone completed!"
echo ""
echo "Next steps:"
echo "1. Remove both microSD cards"
echo "2. Insert the NEW card into your Pi"
echo "3. Boot and run: sudo resize2fs /dev/mmcblk0p2"
echo "4. Run: ./scripts/verify-system.sh"
echo ""
echo "The new card will have all your data and settings!"
