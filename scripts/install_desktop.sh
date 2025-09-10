#!/bin/bash

# Install Desktop Shortcuts for Voice-to-Text System

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Installing desktop shortcuts..."

# Create applications directory if it doesn't exist
mkdir -p ~/.local/share/applications

# Copy desktop files
cp "$PROJECT_DIR/voice-to-text.desktop" ~/.local/share/applications/
cp "$PROJECT_DIR/voice-to-text-manager.desktop" ~/.local/share/applications/

# Make them executable
chmod +x ~/.local/share/applications/voice-to-text.desktop
chmod +x ~/.local/share/applications/voice-to-text-manager.desktop

# Update desktop database
update-desktop-database ~/.local/share/applications

print_success "Desktop shortcuts installed successfully!"
print_status "You can now find 'Voice-to-Text System' and 'Voice-to-Text Manager' in your applications menu."

# Optional: Copy to desktop
read -p "Do you want to create shortcuts on the desktop? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cp "$PROJECT_DIR/voice-to-text.desktop" ~/Desktop/
    cp "$PROJECT_DIR/voice-to-text-manager.desktop" ~/Desktop/
    chmod +x ~/Desktop/voice-to-text.desktop
    chmod +x ~/Desktop/voice-to-text-manager.desktop
    print_success "Desktop shortcuts created on desktop!"
fi

print_status "Installation complete!"
