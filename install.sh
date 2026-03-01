#!/bin/bash

# Voice-to-Text System Installer
# Sets up Python environment, system dependencies, and configuration.

set -e  # Exit on error

GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Voice-to-Text System Installation...${NC}"

# 1. Update and Install System Dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-venv \
    python3-pip \
    python3-dev \
    portaudio19-dev \
    xbindkeys \
    xdotool \
    ffmpeg \
    libgirepository1.0-dev \
    libcairo2-dev \
    gir1.2-gtk-3.0

# 2. Setup Python Virtual Environment
echo "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Virtual environment created at .venv"
else
    echo "Virtual environment already exists."
fi

# Activate venv
source .venv/bin/activate

# 3. Install Python Packages
echo "Installing Python requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Global Hotkey Setup (xbindkeys)
echo "Configuring xbindkeys..."
if [ ! -f ~/.xbindkeysrc ]; then
    echo "Creating default .xbindkeysrc"
    xbindkeys --defaults > ~/.xbindkeysrc
fi

# Note: The application mainly handles hotkeys via pynput now, 
# but xbindkeys is still useful for system-level overrides if needed.

# 5. Create Desktop Entry
echo "Creating desktop shortcut..."
cat <<EOF > ~/.local/share/applications/voice-to-text.desktop
[Desktop Entry]
Name=Voice To Text
Comment=Universal Voice Typing
Exec=$(pwd)/start-voice-to-text.sh
Icon=microphone
Terminal=false
Type=Application
Categories=Utility;Accessibility;
EOF

chmod +x install.sh
chmod +x start-voice-to-text.sh

echo -e "${GREEN}Installation Complete!${NC}"
echo "You can start the app by running: ./start-voice-to-text.sh"
echo "Or find 'Voice To Text' in your application menu."
