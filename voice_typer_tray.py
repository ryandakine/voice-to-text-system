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
        import subprocess
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

def create_icon(status):
    """Create a simple colored circle icon."""
    width = 64
    height = 64
    
    # Green for ON, Red for OFF
    color = "#4CAF50" if status == "ON" else "#F44336"
    
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw filled circle
    margin = 4
    draw.ellipse([margin, margin, width-margin, height-margin], fill=color)
    
    # Add mic symbol (simple circle)
    inner = 20
    draw.ellipse([width//2-inner//2, height//2-inner//2, 
                  width//2+inner//2, height//2+inner//2], 
                 fill="white" if status == "ON" else "#333")
    
    return image

def setup_tray_icon():
    """Setup and run the system tray icon."""
    status = get_status()
    
    # Create menu
    def on_toggle(icon, item):
        toggle_listening()
        update_icon(icon)
    
    def on_exit(icon, item):
        icon.stop()
        sys.exit(0)
    
    menu = pystray.Menu(
        pystray.MenuItem("Toggle Listening", on_toggle),
        pystray.MenuItem("Exit", on_exit)
    )
    
    # Create icon
    icon = pystray.Icon(
        "voice_typer",
        create_icon(status),
        f"VoiceTyper (Listening: {status})",
        menu
    )
    
    # Left click handler
    def on_clicked(icon):
        toggle_listening()
        update_icon(icon)
    
    icon.on_click = on_clicked
    
    # Start status updater thread
    def update_loop():
        last_status = None
        while True:
            time.sleep(0.5)
            new_status = get_status()
            if new_status != last_status:
                last_status = new_status
                update_icon(icon)
    
    Thread(target=update_loop, daemon=True).start()
    
    icon.run()

def update_icon(icon):
    """Update the icon based on current status."""
    status = get_status()
    icon.icon = create_icon(status)
    icon.title = f"VoiceTyper (Listening: {status})"

def main():
    # Check if voice_typer is running
    pid = get_voice_typer_pid()
    if not pid:
        print("Warning: voice_typer.py is not running. Start it first.")
    
    setup_tray_icon()

if __name__ == "__main__":
    main()
