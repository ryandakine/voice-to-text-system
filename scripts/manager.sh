#!/bin/bash

# Voice-to-Text System GUI Manager Launcher

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

# Check if GUI dependencies are available
if ! python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null; then
    echo "Error: GTK3 Python bindings not found. Please install python3-gi."
    exit 1
fi

echo "Starting Voice-to-Text System Manager..."
echo "PID: $$"

# Run the GUI manager
python3 src/gui/manager.py
