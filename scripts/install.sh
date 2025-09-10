#!/bin/bash

# Voice-to-Text System Installation Script
# For Linux Mint and Ubuntu-based systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root"
        exit 1
    fi
}

# Function to update package list
update_packages() {
    print_status "Updating package list..."
    sudo apt update
}

# Function to install system dependencies
install_system_deps() {
    print_status "Installing system dependencies..."
    
    # Audio and system integration
    sudo apt install -y xbindkeys xdotool xclip
    
    # Python and audio libraries
    sudo apt install -y python3-pip python3-pyaudio
    sudo apt install -y libportaudio2 portaudio19-dev
    sudo apt install -y libasound2-dev
    
    # GUI libraries
    sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0
    
    # Development tools
    sudo apt install -y build-essential pkg-config
    
    # Additional utilities
    sudo apt install -y pulseaudio-utils
    
    print_success "System dependencies installed"
}

# Function to install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Upgrade pip
    python3 -m pip install --user --upgrade pip
    
    # Install required packages
    python3 -m pip install --user SpeechRecognition
    python3 -m pip install --user pyaudio
    python3 -m pip install --user openai-whisper
    python3 -m pip install --user PyGObject
    python3 -m pip install --user pynput
    python3 -m pip install --user keyboard
    python3 -m pip install --user psutil
    python3 -m pip install --user numpy
    python3 -m pip install --user soundfile
    python3 -m pip install --user librosa
    python3 -m pip install --user python-xlib
    python3 -m pip install --user pyautogui
    python3 -m pip install --user pyperclip
    
    print_success "Python dependencies installed"
}

# Function to create application directories
create_directories() {
    print_status "Creating application directories..."
    
    # Create config directory
    mkdir -p ~/.config/voice-to-text
    
    # Create logs directory
    mkdir -p ~/.local/share/voice-to-text/logs
    
    # Create cache directory
    mkdir -p ~/.cache/whisper
    
    print_success "Application directories created"
}

# Function to create hotkey trigger script
create_hotkey_script() {
    print_status "Creating hotkey trigger script..."
    
    cat > scripts/hotkey_trigger.sh << 'EOF'
#!/bin/bash

# Hotkey trigger script for voice-to-text system
# This script is called by xbindkeys when the hotkey is pressed

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Send signal to the main application
if [ -f "$PROJECT_DIR/tmp/voice-to-text.pid" ]; then
    PID=$(cat "$PROJECT_DIR/tmp/voice-to-text.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill -USR1 "$PID"
    fi
fi
EOF
    
    chmod +x scripts/hotkey_trigger.sh
    print_success "Hotkey trigger script created"
}

# Function to create systemd service
create_systemd_service() {
    print_status "Creating systemd service..."
    
    # Create systemd user directory
    mkdir -p ~/.config/systemd/user
    
    # Create service file
    cat > ~/.config/systemd/user/voice-to-text.service << EOF
[Unit]
Description=Voice-to-Text System
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=$(which python3) $PWD/src/main.py
WorkingDirectory=$PWD
Restart=always
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=%h/.Xauthority

[Install]
WantedBy=graphical-session.target
EOF
    
    # Reload systemd user daemon
    systemctl --user daemon-reload
    
    print_success "Systemd service created"
}

# Function to create desktop entry
create_desktop_entry() {
    print_status "Creating desktop entry..."
    
    # Create applications directory
    mkdir -p ~/.local/share/applications
    
    # Copy desktop files
    cp "$PWD/voice-to-text.desktop" ~/.local/share/applications/
    cp "$PWD/voice-to-text-manager.desktop" ~/.local/share/applications/
    
    # Make them executable
    chmod +x ~/.local/share/applications/voice-to-text.desktop
    chmod +x ~/.local/share/applications/voice-to-text-manager.desktop
    
    # Update desktop database
    update-desktop-database ~/.local/share/applications
    
    print_success "Desktop entries created"
}

# Function to configure xbindkeys
configure_xbindkeys() {
    print_status "Configuring xbindkeys..."
    
    # Create xbindkeys configuration
    cat > ~/.xbindkeysrc << EOF
# Voice-to-Text System Configuration
# Generated automatically - do not edit manually

# F5 hotkey for voice-to-text
"$PWD/scripts/hotkey_trigger.sh"
    F5

# End of configuration
EOF
    
    print_success "xbindkeys configured"
}

# Function to test installation
test_installation() {
    print_status "Testing installation..."
    
    # Test Python imports
    if python3 -c "import pyaudio, whisper, speech_recognition" 2>/dev/null; then
        print_success "Python dependencies test passed"
    else
        print_error "Python dependencies test failed"
        return 1
    fi
    
    # Test audio devices
    if python3 -c "import pyaudio; p = pyaudio.PyAudio(); print('Audio devices:', p.get_device_count())" 2>/dev/null; then
        print_success "Audio system test passed"
    else
        print_warning "Audio system test failed - check microphone permissions"
    fi
    
    # Test xbindkeys
    if command_exists xbindkeys; then
        print_success "xbindkeys is available"
    else
        print_error "xbindkeys not found"
        return 1
    fi
    
    print_success "Installation test completed"
}

# Function to show usage instructions
show_usage_instructions() {
    echo
    print_success "Installation completed successfully!"
    echo
    echo "Usage Instructions:"
    echo "=================="
    echo
    echo "1. Start the system:"
    echo "   python3 src/main.py"
    echo
    echo "2. Or use the desktop application:"
    echo "   Look for 'Voice-to-Text System' in your applications menu"
    echo
    echo "3. Enable auto-start (optional):"
    echo "   systemctl --user enable voice-to-text.service"
    echo
    echo "4. Press F5 anywhere to start voice recording"
    echo "   Press F5 again to stop recording and insert text"
    echo
    echo "5. Configuration:"
    echo "   Edit ~/.config/voice-to-text/config.ini to customize settings"
    echo
    echo "6. Logs:"
    echo "   Check ~/.local/share/voice-to-text/logs/ for application logs"
    echo
}

# Main installation function
main() {
    echo "Voice-to-Text System Installation"
    echo "================================="
    echo
    
    # Check if not running as root
    check_root
    
    # Check if we're in the right directory
    if [ ! -f "src/main.py" ]; then
        print_error "Please run this script from the voice-to-text-system directory"
        exit 1
    fi
    
    # Update packages
    update_packages
    
    # Install system dependencies
    install_system_deps
    
    # Install Python dependencies
    install_python_deps
    
    # Create directories
    create_directories
    
    # Create scripts
    create_hotkey_script
    
    # Create systemd service
    create_systemd_service
    
    # Create desktop entry
    create_desktop_entry
    
    # Configure xbindkeys
    configure_xbindkeys
    
    # Test installation
    test_installation
    
    # Show usage instructions
    show_usage_instructions
}

# Run main function
main "$@"
