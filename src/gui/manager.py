"""
GUI Manager for the Voice-to-Text System
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import threading
import time
import subprocess
import os
from pathlib import Path

from ..utils.logger import logger
from ..utils.config_manager import config
from ..utils.audio_utils import audio_manager
from ..speech_processor import speech_processor
from ..text_insertion import text_inserter
from ..hotkey_handler import hotkey_handler


class VoiceToTextManager(Gtk.Window):
    """Main GUI manager for the voice-to-text system."""
    
    def __init__(self):
        super().__init__()
        
        self.set_title("Voice-to-Text System Manager")
        self.set_default_size(800, 600)
        self.set_resizable(True)
        
        # Initialize components
        self.system_running = False
        self.recording = False
        self.processing = False
        
        # Create UI
        self._create_ui()
        
        # Start status update thread
        self._start_status_updates()
        
        # Connect signals
        self.connect("delete-event", self._on_window_delete)
        
        logger.info("Voice-to-Text Manager GUI initialized")
    
    def _create_ui(self):
        """Create the main user interface."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        
        # Header
        header_box = self._create_header()
        main_box.pack_start(header_box, False, False, 0)
        
        # Notebook for tabs
        notebook = Gtk.Notebook()
        main_box.pack_start(notebook, True, True, 0)
        
        # Status tab
        status_page = self._create_status_tab()
        notebook.append_page(status_page, Gtk.Label(label="Status"))
        
        # Settings tab
        settings_page = self._create_settings_tab()
        notebook.append_page(settings_page, Gtk.Label(label="Settings"))
        
        # Audio tab
        audio_page = self._create_audio_tab()
        notebook.append_page(audio_page, Gtk.Label(label="Audio"))
        
        # Logs tab
        logs_page = self._create_logs_tab()
        notebook.append_page(logs_page, Gtk.Label(label="Logs"))
        
        # Test tab
        test_page = self._create_test_tab()
        notebook.append_page(test_page, Gtk.Label(label="Test"))
        
        # Footer
        footer_box = self._create_footer()
        main_box.pack_start(footer_box, False, False, 0)
        
        self.add(main_box)
    
    def _create_header(self):
        """Create the header section."""
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<span size='x-large' weight='bold'>Voice-to-Text System Manager</span>")
        header_box.pack_start(title_label, True, True, 0)
        
        # Status indicator
        self.status_indicator = Gtk.Label()
        self.status_indicator.set_markup("<span foreground='red'>●</span> Stopped")
        header_box.pack_start(self.status_indicator, False, False, 0)
        
        # Control buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.start_button = Gtk.Button(label="Start System")
        self.start_button.connect("clicked", self._on_start_clicked)
        button_box.pack_start(self.start_button, False, False, 0)
        
        self.stop_button = Gtk.Button(label="Stop System")
        self.stop_button.connect("clicked", self._on_stop_clicked)
        self.stop_button.set_sensitive(False)
        button_box.pack_start(self.stop_button, False, False, 0)
        
        header_box.pack_start(button_box, False, False, 0)
        
        return header_box
    
    def _create_status_tab(self):
        """Create the status monitoring tab."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        # System status
        status_frame = Gtk.Frame(label="System Status")
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        status_frame.add(status_box)
        
        # Status grid
        status_grid = Gtk.Grid()
        status_grid.set_column_spacing(10)
        status_grid.set_row_spacing(5)
        
        # System running
        status_grid.attach(Gtk.Label(label="System Running:"), 0, 0, 1, 1)
        self.system_status_label = Gtk.Label(label="No")
        status_grid.attach(self.system_status_label, 1, 0, 1, 1)
        
        # Recording status
        status_grid.attach(Gtk.Label(label="Recording:"), 0, 1, 1, 1)
        self.recording_status_label = Gtk.Label(label="No")
        status_grid.attach(self.recording_status_label, 1, 1, 1, 1)
        
        # Processing status
        status_grid.attach(Gtk.Label(label="Processing:"), 0, 2, 1, 1)
        self.processing_status_label = Gtk.Label(label="No")
        status_grid.attach(self.processing_status_label, 1, 2, 1, 1)
        
        # Hotkey
        status_grid.attach(Gtk.Label(label="Hotkey:"), 0, 3, 1, 1)
        self.hotkey_label = Gtk.Label(label=config.get('General', 'hotkey', 'F5'))
        status_grid.attach(self.hotkey_label, 1, 3, 1, 1)
        
        # Whisper model
        status_grid.attach(Gtk.Label(label="Whisper Model:"), 0, 4, 1, 1)
        self.model_label = Gtk.Label(label=config.get('Whisper', 'model', 'base'))
        status_grid.attach(self.model_label, 1, 4, 1, 1)
        
        status_box.pack_start(status_grid, False, False, 0)
        box.pack_start(status_frame, False, False, 0)
        
        # Quick actions
        actions_frame = Gtk.Frame(label="Quick Actions")
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        actions_frame.add(actions_box)
        
        # Test recording button
        self.test_record_button = Gtk.Button(label="Test Recording")
        self.test_record_button.connect("clicked", self._on_test_record_clicked)
        actions_box.pack_start(self.test_record_button, False, False, 0)
        
        # Test transcription button
        self.test_transcribe_button = Gtk.Button(label="Test Transcription")
        self.test_transcribe_button.connect("clicked", self._on_test_transcribe_clicked)
        actions_box.pack_start(self.test_transcribe_button, False, False, 0)
        
        # Test insertion button
        self.test_insert_button = Gtk.Button(label="Test Text Insertion")
        self.test_insert_button.connect("clicked", self._on_test_insert_clicked)
        actions_box.pack_start(self.test_insert_button, False, False, 0)
        
        box.pack_start(actions_frame, False, False, 0)
        
        # Recent activity
        activity_frame = Gtk.Frame(label="Recent Activity")
        activity_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        activity_frame.add(activity_box)
        
        # Activity text view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_min_content_height(200)
        
        self.activity_textview = Gtk.TextView()
        self.activity_textview.set_editable(False)
        self.activity_textview.set_monospace(True)
        
        scrolled_window.add(self.activity_textview)
        activity_box.pack_start(scrolled_window, True, True, 0)
        
        box.pack_start(activity_frame, True, True, 0)
        
        return box
    
    def _create_settings_tab(self):
        """Create the settings configuration tab."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        # General settings
        general_frame = Gtk.Frame(label="General Settings")
        general_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        general_frame.add(general_box)
        
        # Hotkey setting
        hotkey_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hotkey_box.pack_start(Gtk.Label(label="Global Hotkey:"), False, False, 0)
        
        self.hotkey_entry = Gtk.Entry()
        self.hotkey_entry.set_text(config.get('General', 'hotkey', 'F5'))
        hotkey_box.pack_start(self.hotkey_entry, False, False, 0)
        
        general_box.pack_start(hotkey_box, False, False, 0)
        
        # Auto-start setting
        auto_start_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        auto_start_box.pack_start(Gtk.Label(label="Auto-start with system:"), False, False, 0)
        
        self.auto_start_switch = Gtk.Switch()
        self.auto_start_switch.set_active(config.getboolean('General', 'auto_start', True))
        auto_start_box.pack_start(self.auto_start_switch, False, False, 0)
        
        general_box.pack_start(auto_start_box, False, False, 0)
        
        box.pack_start(general_frame, False, False, 0)
        
        # Whisper settings
        whisper_frame = Gtk.Frame(label="Whisper Settings")
        whisper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        whisper_frame.add(whisper_box)
        
        # Model selection
        model_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        model_box.pack_start(Gtk.Label(label="Model:"), False, False, 0)
        
        self.model_combo = Gtk.ComboBoxText()
        models = ['tiny', 'base', 'small', 'medium', 'large']
        for model in models:
            self.model_combo.append_text(model)
        self.model_combo.set_active(models.index(config.get('Whisper', 'model', 'base')))
        model_box.pack_start(self.model_combo, False, False, 0)
        
        whisper_box.pack_start(model_box, False, False, 0)
        
        # Language setting
        language_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        language_box.pack_start(Gtk.Label(label="Language:"), False, False, 0)
        
        self.language_entry = Gtk.Entry()
        self.language_entry.set_text(config.get('Whisper', 'language', 'auto'))
        language_box.pack_start(self.language_entry, False, False, 0)
        
        whisper_box.pack_start(language_box, False, False, 0)
        
        box.pack_start(whisper_frame, False, False, 0)
        
        # Text insertion settings
        insertion_frame = Gtk.Frame(label="Text Insertion Settings")
        insertion_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        insertion_frame.add(insertion_box)
        
        # Primary method
        primary_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        primary_box.pack_start(Gtk.Label(label="Primary Method:"), False, False, 0)
        
        self.primary_method_combo = Gtk.ComboBoxText()
        methods = ['clipboard', 'keyboard', 'xdotool']
        for method in methods:
            self.primary_method_combo.append_text(method)
        self.primary_method_combo.set_active(methods.index(config.get('TextInsertion', 'primary_method', 'clipboard')))
        primary_box.pack_start(self.primary_method_combo, False, False, 0)
        
        insertion_box.pack_start(primary_box, False, False, 0)
        
        # Fallback method
        fallback_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fallback_box.pack_start(Gtk.Label(label="Fallback Method:"), False, False, 0)
        
        self.fallback_method_combo = Gtk.ComboBoxText()
        for method in methods:
            self.fallback_method_combo.append_text(method)
        self.fallback_method_combo.set_active(methods.index(config.get('TextInsertion', 'fallback_method', 'keyboard')))
        fallback_box.pack_start(self.fallback_method_combo, False, False, 0)
        
        insertion_box.pack_start(fallback_box, False, False, 0)
        
        box.pack_start(insertion_frame, False, False, 0)
        
        # Save button
        save_button = Gtk.Button(label="Save Settings")
        save_button.connect("clicked", self._on_save_settings_clicked)
        box.pack_start(save_button, False, False, 0)
        
        return box
    
    def _create_audio_tab(self):
        """Create the audio configuration tab."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        # Audio devices
        devices_frame = Gtk.Frame(label="Audio Devices")
        devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        devices_frame.add(devices_box)
        
        # Device list
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_min_content_height(200)
        
        self.device_liststore = Gtk.ListStore(str, str, str, str)
        self.device_treeview = Gtk.TreeView(model=self.device_liststore)
        
        # Add columns
        renderer = Gtk.CellRendererText()
        col1 = Gtk.TreeViewColumn("Index", renderer, text=0)
        col2 = Gtk.TreeViewColumn("Name", renderer, text=1)
        col3 = Gtk.TreeViewColumn("Channels", renderer, text=2)
        col4 = Gtk.TreeViewColumn("Sample Rate", renderer, text=3)
        
        self.device_treeview.append_column(col1)
        self.device_treeview.append_column(col2)
        self.device_treeview.append_column(col3)
        self.device_treeview.append_column(col4)
        
        scrolled_window.add(self.device_treeview)
        devices_box.pack_start(scrolled_window, True, True, 0)
        
        # Refresh button
        refresh_button = Gtk.Button(label="Refresh Devices")
        refresh_button.connect("clicked", self._on_refresh_devices_clicked)
        devices_box.pack_start(refresh_button, False, False, 0)
        
        box.pack_start(devices_frame, True, True, 0)
        
        # Audio settings
        settings_frame = Gtk.Frame(label="Audio Settings")
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        settings_frame.add(settings_box)
        
        # Sample rate
        rate_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        rate_box.pack_start(Gtk.Label(label="Sample Rate:"), False, False, 0)
        
        self.sample_rate_combo = Gtk.ComboBoxText()
        rates = ['8000', '16000', '22050', '44100', '48000']
        for rate in rates:
            self.sample_rate_combo.append_text(rate)
        current_rate = str(config.getint('Audio', 'sample_rate', 16000))
        if current_rate in rates:
            self.sample_rate_combo.set_active(rates.index(current_rate))
        rate_box.pack_start(self.sample_rate_combo, False, False, 0)
        
        settings_box.pack_start(rate_box, False, False, 0)
        
        box.pack_start(settings_frame, False, False, 0)
        
        return box
    
    def _create_logs_tab(self):
        """Create the logs viewing tab."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        # Log controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # Log level filter
        controls_box.pack_start(Gtk.Label(label="Log Level:"), False, False, 0)
        
        self.log_level_combo = Gtk.ComboBoxText()
        levels = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR']
        for level in levels:
            self.log_level_combo.append_text(level)
        self.log_level_combo.set_active(levels.index('INFO'))
        controls_box.pack_start(self.log_level_combo, False, False, 0)
        
        # Refresh button
        refresh_button = Gtk.Button(label="Refresh Logs")
        refresh_button.connect("clicked", self._on_refresh_logs_clicked)
        controls_box.pack_start(refresh_button, False, False, 0)
        
        # Clear button
        clear_button = Gtk.Button(label="Clear Logs")
        clear_button.connect("clicked", self._on_clear_logs_clicked)
        controls_box.pack_start(clear_button, False, False, 0)
        
        box.pack_start(controls_box, False, False, 0)
        
        # Log text view
        scrolled_window = Gtk.ScrolledWindow()
        
        self.log_textview = Gtk.TextView()
        self.log_textview.set_editable(False)
        self.log_textview.set_monospace(True)
        
        scrolled_window.add(self.log_textview)
        box.pack_start(scrolled_window, True, True, 0)
        
        return box
    
    def _create_test_tab(self):
        """Create the testing tab."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        
        # Test controls
        test_frame = Gtk.Frame(label="System Tests")
        test_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        test_frame.add(test_box)
        
        # Test buttons
        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        test_audio_button = Gtk.Button(label="Test Audio")
        test_audio_button.connect("clicked", self._on_test_audio_clicked)
        buttons_box.pack_start(test_audio_button, False, False, 0)
        
        test_whisper_button = Gtk.Button(label="Test Whisper")
        test_whisper_button.connect("clicked", self._on_test_whisper_clicked)
        buttons_box.pack_start(test_whisper_button, False, False, 0)
        
        test_hotkey_button = Gtk.Button(label="Test Hotkey")
        test_hotkey_button.connect("clicked", self._on_test_hotkey_clicked)
        buttons_box.pack_start(test_hotkey_button, False, False, 0)
        
        test_insertion_button = Gtk.Button(label="Test Insertion")
        test_insertion_button.connect("clicked", self._on_test_insertion_clicked)
        buttons_box.pack_start(test_insertion_button, False, False, 0)
        
        test_box.pack_start(buttons_box, False, False, 0)
        
        # Run all tests button
        run_all_button = Gtk.Button(label="Run All Tests")
        run_all_button.connect("clicked", self._on_run_all_tests_clicked)
        test_box.pack_start(run_all_button, False, False, 0)
        
        box.pack_start(test_frame, False, False, 0)
        
        # Test results
        results_frame = Gtk.Frame(label="Test Results")
        results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        results_frame.add(results_box)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_min_content_height(300)
        
        self.test_results_textview = Gtk.TextView()
        self.test_results_textview.set_editable(False)
        self.test_results_textview.set_monospace(True)
        
        scrolled_window.add(self.test_results_textview)
        results_box.pack_start(scrolled_window, True, True, 0)
        
        box.pack_start(results_frame, True, True, 0)
        
        return box
    
    def _create_footer(self):
        """Create the footer section."""
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # Version info
        version_label = Gtk.Label(label="Version 1.0.0")
        footer_box.pack_start(version_label, False, False, 0)
        
        # Status message
        self.status_message = Gtk.Label(label="Ready")
        footer_box.pack_start(self.status_message, True, True, 0)
        
        # Close button
        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", self._on_close_clicked)
        footer_box.pack_start(close_button, False, False, 0)
        
        return footer_box
    
    def _start_status_updates(self):
        """Start the status update thread."""
        def update_status():
            while True:
                GLib.idle_add(self._update_status_display)
                time.sleep(1)
        
        thread = threading.Thread(target=update_status, daemon=True)
        thread.start()
    
    def _update_status_display(self):
        """Update the status display."""
        try:
            # Update system status
            if self.system_running:
                self.system_status_label.set_text("Yes")
                self.status_indicator.set_markup("<span foreground='green'>●</span> Running")
            else:
                self.system_status_label.set_text("No")
                self.status_indicator.set_markup("<span foreground='red'>●</span> Stopped")
            
            # Update recording status
            if self.recording:
                self.recording_status_label.set_text("Yes")
            else:
                self.recording_status_label.set_text("No")
            
            # Update processing status
            if self.processing:
                self.processing_status_label.set_text("Yes")
            else:
                self.processing_status_label.set_text("No")
            
            # Update device list
            self._update_device_list()
            
        except Exception as e:
            logger.error(f"Error updating status: {e}")
    
    def _update_device_list(self):
        """Update the audio device list."""
        try:
            devices = audio_manager.get_audio_devices()
            
            # Clear existing list
            self.device_liststore.clear()
            
            # Add devices
            for device in devices:
                self.device_liststore.append([
                    str(device['index']),
                    device['name'],
                    str(device['channels']),
                    str(device['sample_rate'])
                ])
                
        except Exception as e:
            logger.error(f"Error updating device list: {e}")
    
    def _add_activity_message(self, message):
        """Add a message to the activity log."""
        textbuffer = self.activity_textview.get_buffer()
        end_iter = textbuffer.get_end_iter()
        textbuffer.insert(end_iter, f"{time.strftime('%H:%M:%S')} - {message}\n")
        
        # Scroll to end
        self.activity_textview.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
    
    def _add_test_result(self, result):
        """Add a test result to the test results."""
        textbuffer = self.test_results_textview.get_buffer()
        end_iter = textbuffer.get_end_iter()
        textbuffer.insert(end_iter, f"{time.strftime('%H:%M:%S')} - {result}\n")
        
        # Scroll to end
        self.test_results_textview.scroll_to_iter(end_iter, 0.0, False, 0.0, 0.0)
    
    # Signal handlers
    def _on_window_delete(self, widget, event):
        """Handle window close event."""
        self.hide()
        return True
    
    def _on_start_clicked(self, widget):
        """Handle start button click."""
        try:
            # Start the system
            self.system_running = True
            self.start_button.set_sensitive(False)
            self.stop_button.set_sensitive(True)
            self._add_activity_message("System started")
            self.status_message.set_text("System started")
            
        except Exception as e:
            logger.error(f"Error starting system: {e}")
            self._add_activity_message(f"Error starting system: {e}")
    
    def _on_stop_clicked(self, widget):
        """Handle stop button click."""
        try:
            # Stop the system
            self.system_running = False
            self.start_button.set_sensitive(True)
            self.stop_button.set_sensitive(False)
            self._add_activity_message("System stopped")
            self.status_message.set_text("System stopped")
            
        except Exception as e:
            logger.error(f"Error stopping system: {e}")
            self._add_activity_message(f"Error stopping system: {e}")
    
    def _on_close_clicked(self, widget):
        """Handle close button click."""
        self.hide()
    
    def _on_save_settings_clicked(self, widget):
        """Handle save settings button click."""
        try:
            # Save general settings
            config.set('General', 'hotkey', self.hotkey_entry.get_text())
            config.set('General', 'auto_start', str(self.auto_start_switch.get_active()))
            
            # Save Whisper settings
            config.set('Whisper', 'model', self.model_combo.get_active_text())
            config.set('Whisper', 'language', self.language_entry.get_text())
            
            # Save text insertion settings
            config.set('TextInsertion', 'primary_method', self.primary_method_combo.get_active_text())
            config.set('TextInsertion', 'fallback_method', self.fallback_method_combo.get_active_text())
            
            # Save audio settings
            config.set('Audio', 'sample_rate', self.sample_rate_combo.get_active_text())
            
            config.save_config()
            
            self._add_activity_message("Settings saved")
            self.status_message.set_text("Settings saved")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            self._add_activity_message(f"Error saving settings: {e}")
    
    def _on_test_record_clicked(self, widget):
        """Handle test recording button click."""
        self._add_activity_message("Test recording started")
        # Implementation would go here
    
    def _on_test_transcribe_clicked(self, widget):
        """Handle test transcription button click."""
        self._add_activity_message("Test transcription started")
        # Implementation would go here
    
    def _on_test_insert_clicked(self, widget):
        """Handle test insertion button click."""
        self._add_activity_message("Test insertion started")
        # Implementation would go here
    
    def _on_refresh_devices_clicked(self, widget):
        """Handle refresh devices button click."""
        self._update_device_list()
        self._add_activity_message("Audio devices refreshed")
    
    def _on_refresh_logs_clicked(self, widget):
        """Handle refresh logs button click."""
        self._add_activity_message("Logs refreshed")
        # Implementation would go here
    
    def _on_clear_logs_clicked(self, widget):
        """Handle clear logs button click."""
        self._add_activity_message("Logs cleared")
        # Implementation would go here
    
    def _on_test_audio_clicked(self, widget):
        """Handle test audio button click."""
        self._add_test_result("Testing audio system...")
        # Implementation would go here
    
    def _on_test_whisper_clicked(self, widget):
        """Handle test Whisper button click."""
        self._add_test_result("Testing Whisper...")
        # Implementation would go here
    
    def _on_test_hotkey_clicked(self, widget):
        """Handle test hotkey button click."""
        self._add_test_result("Testing hotkey...")
        # Implementation would go here
    
    def _on_test_insertion_clicked(self, widget):
        """Handle test insertion button click."""
        self._add_test_result("Testing text insertion...")
        # Implementation would go here
    
    def _on_run_all_tests_clicked(self, widget):
        """Handle run all tests button click."""
        self._add_test_result("Running all tests...")
        # Implementation would go here


def main():
    """Main function to run the GUI manager."""
    window = VoiceToTextManager()
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
