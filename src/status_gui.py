import sys
import os
import subprocess

# Ensure we can find system packages
sys.path.append('/usr/lib/python3/dist-packages')

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango

class StatusWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Voice to Text Status")
        self.set_border_width(10)
        self.set_default_size(300, 150)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # Status Label
        self.status_label = Gtk.Label()
        self.status_label.set_use_markup(True)
        # Increase font size
        self.status_label.override_font(Pango.FontDescription("Sans 14"))
        vbox.pack_start(self.status_label, True, True, 0)

        # Buttons Box
        bbox = Gtk.Box(spacing=6)
        vbox.pack_start(bbox, False, False, 0)

        self.start_btn = Gtk.Button(label="Start")
        self.start_btn.connect("clicked", self.on_start_clicked)
        bbox.pack_start(self.start_btn, True, True, 0)

        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.connect("clicked", self.on_stop_clicked)
        bbox.pack_start(self.stop_btn, True, True, 0)

        self.restart_btn = Gtk.Button(label="Restart")
        self.restart_btn.connect("clicked", self.on_restart_clicked)
        bbox.pack_start(self.restart_btn, True, True, 0)

        # Initial update
        self.update_status()
        
        # Update every 2 seconds
        GLib.timeout_add_seconds(2, self.update_status)

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
            self.status_label.set_markup("<span foreground='green' weight='bold'>Running</span>")
            self.start_btn.set_sensitive(False)
            self.stop_btn.set_sensitive(True)
            self.restart_btn.set_sensitive(True)
        elif status == "inactive":
            self.status_label.set_markup("<span foreground='red' weight='bold'>Stopped</span>")
            self.start_btn.set_sensitive(True)
            self.stop_btn.set_sensitive(False)
            self.restart_btn.set_sensitive(False)
        elif status == "activating":
            self.status_label.set_markup("<span foreground='orange' weight='bold'>Starting...</span>")
            self.start_btn.set_sensitive(False)
            self.stop_btn.set_sensitive(True)
            self.restart_btn.set_sensitive(False)
        elif status == "deactivating":
            self.status_label.set_markup("<span foreground='orange' weight='bold'>Stopping...</span>")
            self.start_btn.set_sensitive(False)
            self.stop_btn.set_sensitive(False)
            self.restart_btn.set_sensitive(False)
        else:
            self.status_label.set_markup(f"<span foreground='gray' weight='bold'>{status}</span>")
            self.start_btn.set_sensitive(True)
            self.stop_btn.set_sensitive(True)
            self.restart_btn.set_sensitive(True)
        return True # Keep timer running

    def run_systemctl(self, action):
        # Disable buttons temporarily
        self.start_btn.set_sensitive(False)
        self.stop_btn.set_sensitive(False)
        self.restart_btn.set_sensitive(False)
        self.status_label.set_markup("<span foreground='blue'>Processing...</span>")
        
        # Run in background to not freeze GUI
        subprocess.Popen(["systemctl", "--user", action, "voice-to-text.service"])
        
        # Force an update check soon
        GLib.timeout_add(500, self.update_status)

    def on_start_clicked(self, widget):
        self.run_systemctl("start")

    def on_stop_clicked(self, widget):
        self.run_systemctl("stop")

    def on_restart_clicked(self, widget):
        self.run_systemctl("restart")

win = StatusWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
