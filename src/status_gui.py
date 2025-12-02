import sys
import os
import subprocess
import time
import threading
from pathlib import Path

# Add project root to path to allow imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure we can find system packages (for Gtk)
sys.path.append('/usr/lib/python3/dist-packages')

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango, Gdk

# Import config manager
try:
    from src.utils.config_manager import config
except ImportError:
    # Fallback if running directly from src
    sys.path.append(str(Path(__file__).parent))
    from utils.config_manager import config

class DashboardWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Voice Control Dashboard")
        self.set_border_width(20)
        self.set_default_size(400, 250)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        # Custom CSS for styling
        css_provider = Gtk.CssProvider()
        css = b"""
        window { background-color: #f5f5f5; }
        label { color: #333333; }
        .status-label { font-weight: bold; font-size: 16px; }
        .section-label { font-weight: bold; color: #555555; margin-bottom: 5px; }
        .card { background-color: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        """
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), 
            css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Main Layout
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.add(main_vbox)

        # --- Service Control Section ---
        service_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        service_frame.get_style_context().add_class("card")
        main_vbox.pack_start(service_frame, False, False, 0)

        # Header
        service_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        service_frame.pack_start(service_header, False, False, 0)
        
        lbl_service = Gtk.Label(label="System Status")
        lbl_service.get_style_context().add_class("section-label")
        lbl_service.set_halign(Gtk.Align.START)
        service_header.pack_start(lbl_service, True, True, 0)

        # Status Row
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        service_frame.pack_start(status_row, False, False, 0)

        self.status_label = Gtk.Label(label="Checking...")
        self.status_label.get_style_context().add_class("status-label")
        self.status_label.set_halign(Gtk.Align.START)
        status_row.pack_start(self.status_label, True, True, 0)

        self.service_switch = Gtk.Switch()
        self.service_switch.set_valign(Gtk.Align.CENTER)
        self.service_switch.connect("state-set", self.on_service_switch_toggled)
        status_row.pack_end(self.service_switch, False, False, 0)

        # --- Performance Section ---
        perf_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        perf_frame.get_style_context().add_class("card")
        main_vbox.pack_start(perf_frame, False, False, 0)

        # Header
        perf_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        perf_frame.pack_start(perf_header, False, False, 0)

        lbl_perf = Gtk.Label(label="Performance Mode")
        lbl_perf.get_style_context().add_class("section-label")
        lbl_perf.set_halign(Gtk.Align.START)
        perf_header.pack_start(lbl_perf, True, True, 0)

        # Eco Mode Row
        eco_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        perf_frame.pack_start(eco_row, False, False, 0)

        eco_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        eco_lbl = Gtk.Label(label="Low Power Mode")
        eco_lbl.set_halign(Gtk.Align.START)
        eco_desc = Gtk.Label(label="Uses 'tiny' model to save RAM/CPU")
        eco_desc.set_halign(Gtk.Align.START)
        eco_desc.override_font(Pango.FontDescription("Sans 8"))
        eco_desc.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.5, 0.5, 0.5, 1))
        
        eco_vbox.pack_start(eco_lbl, False, False, 0)
        eco_vbox.pack_start(eco_desc, False, False, 0)
        eco_row.pack_start(eco_vbox, True, True, 0)

        self.eco_switch = Gtk.Switch()
        self.eco_switch.set_valign(Gtk.Align.CENTER)
        self.eco_switch.connect("state-set", self.on_eco_switch_toggled)
        eco_row.pack_end(self.eco_switch, False, False, 0)

        # --- Footer ---
        self.info_label = Gtk.Label(label="")
        self.info_label.override_font(Pango.FontDescription("Sans 9"))
        self.info_label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.4, 0.4, 0.4, 1))
        main_vbox.pack_end(self.info_label, False, False, 0)

        # State tracking
        self.updating = False
        
        # Initial checks
        self.check_status()
        self.check_model()
        
        # Start timer
        GLib.timeout_add_seconds(2, self.check_status)

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

    def check_status(self):
        if self.updating: return True
        
        status = self.get_service_status()
        self.updating = True
        
        if status == "active":
            self.status_label.set_markup("<span foreground='#2ecc71'>● Running</span>")
            self.service_switch.set_state(True)
        elif status == "inactive" or status == "failed":
            self.status_label.set_markup("<span foreground='#e74c3c'>● Stopped</span>")
            self.service_switch.set_state(False)
        elif status == "activating":
            self.status_label.set_markup("<span foreground='#f39c12'>● Starting...</span>")
            self.service_switch.set_state(True)
        elif status == "deactivating":
            self.status_label.set_markup("<span foreground='#f39c12'>● Stopping...</span>")
            self.service_switch.set_state(False)
        else:
            self.status_label.set_text(f"Status: {status}")
            
        self.updating = False
        return True

    def check_model(self):
        # Read config directly to avoid caching issues
        try:
            current_model = config.get('Whisper', 'model', 'base')
            self.updating = True
            if current_model == 'tiny':
                self.eco_switch.set_state(True)
                self.info_label.set_text("Current Model: Tiny (Fast, Low RAM)")
            else:
                self.eco_switch.set_state(False)
                self.info_label.set_text(f"Current Model: {current_model.capitalize()} (Better Accuracy)")
            self.updating = False
        except Exception as e:
            print(f"Error checking model: {e}")

    def on_service_switch_toggled(self, switch, state):
        if self.updating: return
        
        action = "start" if state else "stop"
        self.status_label.set_text("Processing...")
        
        def run_cmd():
            subprocess.run(["systemctl", "--user", action, "voice-to-text.service"])
            GLib.idle_add(self.check_status)
            
        threading.Thread(target=run_cmd).start()
        return True # Stop propagation to prevent immediate state flip visual glitch

    def on_eco_switch_toggled(self, switch, state):
        if self.updating: return

        new_model = "tiny" if state else "base"
        self.info_label.set_text(f"Switching to {new_model}...")
        
        def switch_model():
            # Update config
            config.update_whisper_model(new_model)
            
            # Restart service if running
            if self.service_switch.get_active():
                subprocess.run(["systemctl", "--user", "restart", "voice-to-text.service"])
            
            GLib.idle_add(self.check_model)
            GLib.idle_add(self.check_status)
            
        threading.Thread(target=switch_model).start()
        return True

if __name__ == "__main__":
    win = DashboardWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
