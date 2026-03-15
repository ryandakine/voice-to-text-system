#!/usr/bin/env python3
"""System tray indicator for VoiceTyper.

Shows an icon in the system tray (toolbar) with toggle functionality.
Right-click for menu, left-click to toggle.
"""

import os
import signal
import sys
from threading import Thread
import time
import subprocess

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "pillow", "-q"])
    import pystray
    from PIL import Image, ImageDraw

# Global state
current_status = "ON"

# Provider config
CONFIG_DIR = os.path.expanduser("~/.voice_typer")
PROVIDER_FILE = os.path.join(CONFIG_DIR, "provider.txt")

def ensure_config_dir():
    """Ensure config directory exists."""
    os.makedirs(CONFIG_DIR, exist_ok=True)

def get_provider():
    """Get current transcription provider."""
    ensure_config_dir()
    try:
        with open(PROVIDER_FILE, "r") as f:
            return f.read().strip()
    except:
        return "deepgram"  # Default

def set_provider(provider):
    """Set transcription provider."""
    ensure_config_dir()
    with open(PROVIDER_FILE, "w") as f:
        f.write(provider)

def get_voice_typer_pid():
    """Get the PID of running voice_typer.py."""
    lock_file = "/tmp/voice_typer.pid"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                return int(f.read().strip())
        except:
            pass
    
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python.*voice_typer.py"],
            capture_output=True,
            text=True
        )
        pids = [p for p in result.stdout.strip().split("\n") if p]
        if pids:
            return int(pids[0])
    except:
        pass
    return None

def get_status():
    """Get current listening status."""
    global current_status
    try:
        with open("/tmp/voice_typer_status", "r") as f:
            current_status = f.read().strip()
            return current_status
    except:
        return current_status

def toggle_listening():
    """Toggle listening state via SIGUSR1."""
    pid = get_voice_typer_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGUSR1)
        except Exception as e:
            print(f"Error toggling: {e}")

def restart_voice_typer():
    """Restart voice_typer with new provider."""
    # Kill existing
    pid = get_voice_typer_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
        except:
            pass
    
    # Start new
    provider = get_provider()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if provider == "whisper":
        # Start Whisper version
        subprocess.Popen(
            [sys.executable, "launcher.py"],
            cwd=script_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    else:
        # Start Deepgram version
        subprocess.Popen(
            [sys.executable, "voice_typer.py"],
            cwd=script_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

def create_icon(status, provider="deepgram"):
    """Create a colored circle icon with provider indicator."""
    width = 64
    height = 64
    
    # Green for ON, Red for OFF
    if status == "ON":
        color = "#4CAF50" if provider == "deepgram" else "#2196F3"  # Green for Deepgram, Blue for Whisper
    else:
        color = "#F44336"  # Red for OFF
    
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw filled circle
    margin = 4
    draw.ellipse([margin, margin, width-margin, height-margin], fill=color)
    
    # Add letter indicator (D or W)
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    letter = "D" if provider == "deepgram" else "W"
    bbox = draw.textbbox((0, 0), letter, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2 - 2
    
    draw.text((text_x, text_y), letter, fill="white", font=font)
    
    return image

def setup_tray_icon():
    """Setup and run the system tray icon."""
    status = get_status()
    provider = get_provider()
    
    # Create menu
    def on_toggle(icon, item):
        toggle_listening()
        update_icon(icon)
    
    def on_switch_to_deepgram(icon, item):
        if get_provider() != "deepgram":
            set_provider("deepgram")
            restart_voice_typer()
            update_icon(icon)
    
    def on_switch_to_whisper(icon, item):
        if get_provider() != "whisper":
            set_provider("whisper")
            restart_voice_typer()
            update_icon(icon)
    
    def on_exit(icon, item):
        icon.stop()
        sys.exit(0)
    
    # Create dynamic menu
    def get_menu():
        provider = get_provider()
        
        return pystray.Menu(
            pystray.MenuItem("Toggle Listening", on_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "☑ Deepgram (Cloud)" if provider == "deepgram" else "   Deepgram (Cloud)",
                on_switch_to_deepgram
            ),
            pystray.MenuItem(
                "☑ Whisper (Local)" if provider == "whisper" else "   Whisper (Local)",
                on_switch_to_whisper
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", on_exit)
        )
    
    # Create icon
    icon = pystray.Icon(
        "voice_typer",
        create_icon(status, provider),
        f"VoiceTyper ({provider.upper()}) - {status}",
        menu=get_menu()
    )
    
    # Left click handler
    def on_clicked(icon):
        toggle_listening()
        update_icon(icon)
    
    icon.on_click = on_clicked
    
    # Start status updater thread
    def update_loop():
        last_status = None
        last_provider = None
        while True:
            time.sleep(0.5)
            new_status = get_status()
            new_provider = get_provider()
            
            if new_status != last_status or new_provider != last_provider:
                last_status = new_status
                last_provider = new_provider
                update_icon(icon)
                # Refresh menu to show checkmarks
                icon.menu = get_menu()
    
    Thread(target=update_loop, daemon=True).start()
    
    icon.run()

def update_icon(icon):
    """Update the icon based on current status."""
    status = get_status()
    provider = get_provider()
    icon.icon = create_icon(status, provider)
    icon.title = f"VoiceTyper ({provider.upper()}) - {status}"

def main():
    # Check if voice_typer is running
    pid = get_voice_typer_pid()
    if not pid:
        print("Warning: voice_typer.py is not running. Start it first.")
    
    setup_tray_icon()

if __name__ == "__main__":
    main()
