#!/bin/bash

# Voice-to-Text System Start Script

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    exit 1
fi

# Check if main.py exists
if [ ! -f "src/main.py" ]; then
    echo "Error: src/main.py not found. Please run this script from the voice-to-text-system directory."
    exit 1
fi

# Create tmp directory if it doesn't exist
mkdir -p tmp

# Save PID to file
echo $$ > tmp/voice-to-text.pid

echo "Starting Voice-to-Text System..."
echo "Press Ctrl+C to stop"
echo "PID: $$"

# Run the main application
python3 src/main.py

# Clean up PID file
rm -f tmp/voice-to-text.pid
