#!/usr/bin/env python3
import time
import os
import signal
import subprocess
import threading
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# Configuration
STATUS_FILE = "/tmp/voice_typer_status"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTROL_SCRIPT = os.path.join(SCRIPT_DIR, "control-voice-typer.sh")

# Global icon reference
icon = None
current_state = "OFF"

def create_image(color):
    """Create a 64x64 circle icon of the given color."""
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (0, 0, 0, 0)) # Transparent logic handled by tray
    # Actually pystray handles transparency if RGBA
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, 56, 56), fill=color)
    return image

def get_state():
    """Read the status file."""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                return f.read().strip()
    except:
        pass
    return "OFF"

def on_clicked(icon, item):
    """Toggle listening when clicked."""
    subprocess.Popen([CONTROL_SCRIPT, "toggle"])
    # Icon update happens in loop
    
def monitor_loop(icon):
    """Poll status file and update icon."""
    global current_state
    icon.visible = True
    while icon.visible:
        new_state = get_state()
        if new_state != current_state:
            current_state = new_state
            if current_state == "ON":
                icon.icon = create_image("green")
                icon.title = "Voice Typer: LISTENING"
            else:
                icon.icon = create_image("red")
                icon.title = "Voice Typer: PAUSED"
        time.sleep(0.5)

def on_quit(icon, item):
    icon.stop()

# Initial setup
image = create_image("red")
menu = pystray.Menu(
    item('Toggle', on_clicked, default=True),
    item('Quit Tray', on_quit)
)

icon = pystray.Icon("voice_typer", image, "Voice Typer: Initializing...", menu)
# Run the monitor in the background thread provided by pystray's setup if needed, 
# or just run our own thread. Pystray 'run' blocks.
# We'll use 'setup' callback to start our monitor thread
icon.run(setup=monitor_loop)
