#!/bin/bash

# Configuration
LOG_FILE="nohup.out"

# Trap signals to properly clean up
cleanup() {
    echo "Stopping bot process..."
    if [ -n "$BOT_PID" ]; then
        kill -TERM "$BOT_PID" 2>/dev/null
        wait "$BOT_PID" 2>/dev/null
    fi
    exit 0
}

# Set up signal trapping
trap cleanup SIGINT SIGTERM

# Start the bot in the background and capture PID
echo "Starting bot in background..."
nohup ./main.py >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

echo "Bot started with PID: $BOT_PID"
echo "Logs being written to: $LOG_FILE"
echo "Press Ctrl+C to stop the bot"

# Wait for the bot process to exit
wait "$BOT_PID"