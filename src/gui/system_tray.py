"""
System tray icon for the voice-to-text system.
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib
import threading
import time

from ..utils.logger import logger
from ..utils.config_manager import config


class SystemTray:
    """System tray icon for the voice-to-text system."""
    
    def __init__(self):
        self.indicator = None
        self.menu = None
        self.is_recording = False
        self.is_processing = False
        
        # Try to use AppIndicator3, fallback to StatusIcon
        try:
            from gi.repository import AppIndicator3
            self._create_app_indicator()
        except ImportError:
            self._create_status_icon()
        
        logger.info("System tray initialized")
    
    def _create_app_indicator(self):
        """Create AppIndicator3 system tray icon."""
        try:
            from gi.repository import AppIndicator3
            
            self.indicator = AppIndicator3.Indicator.new(
                "voice-to-text-system",
                "audio-input-microphone",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self._create_menu()
            self.indicator.set_menu(self.menu)
            
        except Exception as e:
            logger.error(f"Failed to create AppIndicator: {e}")
            self._create_status_icon()
    
    def _create_status_icon(self):
        """Create GTK StatusIcon as fallback."""
        try:
            self.status_icon = Gtk.StatusIcon()
            self.status_icon.set_from_icon_name("audio-input-microphone")
            self.status_icon.set_tooltip_text("Voice-to-Text System")
            self.status_icon.connect("activate", self._on_status_icon_activate)
            self.status_icon.connect("popup-menu", self._on_status_icon_popup)
            
            # Create menu
            self._create_menu()
            
        except Exception as e:
            logger.error(f"Failed to create StatusIcon: {e}")
    
    def _create_menu(self):
        """Create the system tray menu."""
        self.menu = Gtk.Menu()
        
        # Status item
        self.status_item = Gtk.MenuItem(label="Status: Stopped")
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # Start/Stop item
        self.start_stop_item = Gtk.MenuItem(label="Start System")
        self.start_stop_item.connect("activate", self._on_start_stop_clicked)
        self.menu.append(self.start_stop_item)
        
        # Settings item
        settings_item = Gtk.MenuItem(label="Settings")
        settings_item.connect("activate", self._on_settings_clicked)
        self.menu.append(settings_item)
        
        # Test item
        test_item = Gtk.MenuItem(label="Test System")
        test_item.connect("activate", self._on_test_clicked)
        self.menu.append(test_item)
        
        self.menu.append(Gtk.SeparatorMenuItem())
        
        # About item
        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", self._on_about_clicked)
        self.menu.append(about_item)
        
        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit_clicked)
        self.menu.append(quit_item)
        
        self.menu.show_all()
    
    def _on_status_icon_activate(self, widget):
        """Handle status icon activation."""
        self._show_status_dialog()
    
    def _on_status_icon_popup(self, widget, button, time):
        """Handle status icon popup menu."""
        self.menu.popup(None, None, None, None, button, time)
    
    def _on_start_stop_clicked(self, widget):
        """Handle start/stop menu item click."""
        if self.start_stop_item.get_label() == "Start System":
            self.start_system()
        else:
            self.stop_system()
    
    def _on_settings_clicked(self, widget):
        """Handle settings menu item click."""
        self._show_settings_dialog()
    
    def _on_test_clicked(self, widget):
        """Handle test menu item click."""
        self._show_test_dialog()
    
    def _on_about_clicked(self, widget):
        """Handle about menu item click."""
        self._show_about_dialog()
    
    def _on_quit_clicked(self, widget):
        """Handle quit menu item click."""
        self.quit()
    
    def start_system(self):
        """Start the voice-to-text system."""
        try:
            # Update menu
            self.start_stop_item.set_label("Stop System")
            self.status_item.set_label("Status: Running")
            
            # Update icon
            self._update_icon("audio-input-microphone", "System Running")
            
            logger.info("System started via system tray")
            
        except Exception as e:
            logger.error(f"Error starting system: {e}")
    
    def stop_system(self):
        """Stop the voice-to-text system."""
        try:
            # Update menu
            self.start_stop_item.set_label("Start System")
            self.status_item.set_label("Status: Stopped")
            
            # Update icon
            self._update_icon("audio-input-microphone", "System Stopped")
            
            logger.info("System stopped via system tray")
            
        except Exception as e:
            logger.error(f"Error stopping system: {e}")
    
    def set_recording_status(self, recording):
        """Set recording status."""
        self.is_recording = recording
        
        if recording:
            self._update_icon("audio-input-microphone-sensitivity-high", "Recording...")
        else:
            self._update_icon("audio-input-microphone", "System Running")
    
    def set_processing_status(self, processing):
        """Set processing status."""
        self.is_processing = processing
        
        if processing:
            self._update_icon("system-run", "Processing...")
        else:
            if self.is_recording:
                self._update_icon("audio-input-microphone-sensitivity-high", "Recording...")
            else:
                self._update_icon("audio-input-microphone", "System Running")
    
    def _update_icon(self, icon_name, tooltip):
        """Update the system tray icon."""
        try:
            if hasattr(self, 'indicator'):
                # AppIndicator3
                self.indicator.set_icon_full(icon_name, tooltip)
            elif hasattr(self, 'status_icon'):
                # StatusIcon
                self.status_icon.set_from_icon_name(icon_name)
                self.status_icon.set_tooltip_text(tooltip)
        except Exception as e:
            logger.error(f"Error updating icon: {e}")
    
    def _show_status_dialog(self):
        """Show status dialog."""
        dialog = Gtk.Dialog("Voice-to-Text System Status", None, 0,
                           (Gtk.STOCK_OK, Gtk.ResponseType.OK))
        
        dialog.set_default_size(300, 200)
        
        # Status information
        box = dialog.get_content_area()
        
        status_label = Gtk.Label()
        if self.start_stop_item.get_label() == "Stop System":
            status_label.set_markup("<b>System Status: Running</b>")
        else:
            status_label.set_markup("<b>System Status: Stopped</b>")
        
        box.pack_start(status_label, False, False, 10)
        
        # Hotkey info
        hotkey_label = Gtk.Label(f"Hotkey: {config.get('General', 'hotkey', 'F5')}")
        box.pack_start(hotkey_label, False, False, 5)
        
        # Model info
        model_label = Gtk.Label(f"Whisper Model: {config.get('Whisper', 'model', 'base')}")
        box.pack_start(model_label, False, False, 5)
        
        dialog.show_all()
        dialog.run()
        dialog.destroy()
    
    def _show_settings_dialog(self):
        """Show settings dialog."""
        # This would launch the main GUI manager
        logger.info("Opening settings dialog")
        # Implementation would launch the GUI manager
    
    def _show_test_dialog(self):
        """Show test dialog."""
        dialog = Gtk.Dialog("Test Voice-to-Text System", None, 0,
                           (Gtk.STOCK_OK, Gtk.ResponseType.OK))
        
        dialog.set_default_size(400, 300)
        
        box = dialog.get_content_area()
        
        # Test instructions
        instructions = Gtk.Label()
        instructions.set_markup("""
<b>Test Instructions:</b>

1. Click 'Test Recording' to test microphone
2. Click 'Test Transcription' to test Whisper
3. Click 'Test Insertion' to test text insertion
4. Press F5 to test the complete workflow

Make sure you have a text field focused before testing insertion.
        """)
        instructions.set_line_wrap(True)
        box.pack_start(instructions, False, False, 10)
        
        # Test buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        test_record_button = Gtk.Button(label="Test Recording")
        test_record_button.connect("clicked", self._on_test_recording)
        button_box.pack_start(test_record_button, False, False, 0)
        
        test_transcribe_button = Gtk.Button(label="Test Transcription")
        test_transcribe_button.connect("clicked", self._on_test_transcription)
        button_box.pack_start(test_transcribe_button, False, False, 0)
        
        test_insert_button = Gtk.Button(label="Test Insertion")
        test_insert_button.connect("clicked", self._on_test_insertion)
        button_box.pack_start(test_insert_button, False, False, 0)
        
        box.pack_start(button_box, False, False, 10)
        
        dialog.show_all()
        dialog.run()
        dialog.destroy()
    
    def _show_about_dialog(self):
        """Show about dialog."""
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_name("Voice-to-Text System")
        about_dialog.set_version("1.0.0")
        about_dialog.set_copyright("© 2024 System Administrator")
        about_dialog.set_comments("System-wide voice-to-text with global hotkey support")
        about_dialog.set_website("https://github.com/your-repo/voice-to-text-system")
        about_dialog.set_license_type(Gtk.License.MIT_X11)
        
        about_dialog.run()
        about_dialog.destroy()
    
    def _on_test_recording(self, widget):
        """Handle test recording button."""
        logger.info("Test recording requested")
        # Implementation would test recording
    
    def _on_test_transcription(self, widget):
        """Handle test transcription button."""
        logger.info("Test transcription requested")
        # Implementation would test transcription
    
    def _on_test_insertion(self, widget):
        """Handle test insertion button."""
        logger.info("Test insertion requested")
        # Implementation would test insertion
    
    def quit(self):
        """Quit the system tray."""
        try:
            if hasattr(self, 'indicator'):
                self.indicator.set_status(0)  # Hide indicator
            elif hasattr(self, 'status_icon'):
                self.status_icon.set_visible(False)
            
            logger.info("System tray quit")
            
        except Exception as e:
            logger.error(f"Error quitting system tray: {e}")
    
    def show(self):
        """Show the system tray icon."""
        try:
            if hasattr(self, 'status_icon'):
                self.status_icon.set_visible(True)
        except Exception as e:
            logger.error(f"Error showing system tray: {e}")
    
    def hide(self):
        """Hide the system tray icon."""
        try:
            if hasattr(self, 'status_icon'):
                self.status_icon.set_visible(False)
        except Exception as e:
            logger.error(f"Error hiding system tray: {e}")


# Global system tray instance
system_tray = SystemTray()
