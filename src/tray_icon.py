import sys
import os
import signal
import subprocess

# Ensure we can find system packages for AppIndicator
sys.path.append('/usr/lib/python3/dist-packages')

# Ensure GI can find the typelibs
typelib_paths = [
    '/usr/lib/x86_64-linux-gnu/girepository-1.0',
    '/usr/lib/girepository-1.0'
]
os.environ['GI_TYPELIB_PATH'] = ':'.join(typelib_paths) + ':' + os.environ.get('GI_TYPELIB_PATH', '')

import gi
gi.require_version('Gtk', '3.0')

try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3 as AppIndicator
    except (ValueError, ImportError):
        print("Neither AyatanaAppIndicator3 nor AppIndicator3 found.")
        sys.exit(1)

from gi.repository import Gtk, GLib

APPINDICATOR_ID = 'voice-to-text-tray'

class VoiceTray:
    def __init__(self):
        self.indicator = AppIndicator.Indicator.new(
            APPINDICATOR_ID,
            'microphone-sensitivity-muted',
            AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.build_menu())
        
        # Initial update
        self.update_status()
        
        # Update every 2 seconds
        GLib.timeout_add_seconds(2, self.update_status)

    def build_menu(self):
        menu = Gtk.Menu()

        # Status Item (Label)
        self.status_item = Gtk.MenuItem(label="Status: Checking...")
        self.status_item.set_sensitive(False)
        menu.append(self.status_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Start
        self.start_item = Gtk.MenuItem(label="Start Service")
        self.start_item.connect('activate', self.on_start)
        menu.append(self.start_item)

        # Stop
        self.stop_item = Gtk.MenuItem(label="Stop Service")
        self.stop_item.connect('activate', self.on_stop)
        menu.append(self.stop_item)

        # Restart
        self.restart_item = Gtk.MenuItem(label="Restart Service")
        self.restart_item.connect('activate', self.on_restart)
        menu.append(self.restart_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit
        item_quit = Gtk.MenuItem(label="Quit Tray")
        item_quit.connect('activate', self.quit)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def get_service_status(self):
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "voice-to-text.service"],
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def update_status(self):
        status = self.get_service_status()
        
        if status == "active":
            self.indicator.set_icon("microphone-sensitivity-high")
            self.status_item.set_label("Status: Running")
            self.start_item.set_sensitive(False)
            self.stop_item.set_sensitive(True)
        elif status == "activating":
            self.indicator.set_icon("microphone-sensitivity-medium")
            self.status_item.set_label("Status: Starting...")
            self.start_item.set_sensitive(False)
            self.stop_item.set_sensitive(True)
        else:
            self.indicator.set_icon("microphone-sensitivity-muted")
            self.status_item.set_label("Status: Stopped")
            self.start_item.set_sensitive(True)
            self.stop_item.set_sensitive(False)
        
        return True

    def run_command(self, action):
        subprocess.Popen(["systemctl", "--user", action, "voice-to-text.service"])
        # Quick update
        GLib.timeout_add(500, self.update_status)

    def on_start(self, _):
        self.run_command("start")

    def on_stop(self, _):
        self.run_command("stop")

    def on_restart(self, _):
        self.run_command("restart")

    def quit(self, _):
        Gtk.main_quit()

if __name__ == "__main__":
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    tray = VoiceTray()
    Gtk.main()
