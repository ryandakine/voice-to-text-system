#!/bin/bash

# Voice-to-Text Build Script
# Creates a standalone executable using PyInstaller

set -e

GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Build Process...${NC}"

# 1. Activate Virtual Environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found. Run ./install.sh first."
    exit 1
fi

# 2. Install PyInstaller
echo "Installing PyInstaller..."
pip install pyinstaller

# 3. Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist *.spec

# 4. Build Executable
# We need to collect data files and hidden imports
echo "Building executable..."
pyinstaller --noconfirm --clean \
    --name "voice-to-text" \
    --onefile \
    --windowed \
    --collect-all "whisper" \
    --collect-all "pynput" \
    --hidden-import "pynput.keyboard._xorg" \
    --hidden-import "pynput.mouse._xorg" \
    --add-data "src/health_integration/health_config.json:src/health_integration" \
    src/main.py

echo -e "${GREEN}Build Complete!${NC}"
echo "Find your executable at: dist/voice-to-text"
echo "You can copy this file to any Linux Mint/Ubuntu machine and run it."
