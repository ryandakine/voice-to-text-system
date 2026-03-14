#!/usr/bin/env python3
"""Simple toggle button GUI for VoiceTyper.

Shows a small window with an ON/OFF button to control voice recognition.
Click to toggle, or use F8 as before.
"""

import os
import signal
import sys
import tkinter as tk
from tkinter import ttk

def get_voice_typer_pid():
    """Get the PID of running voice_typer.py."""
    lock_file = "/tmp/voice_typer.pid"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                return int(f.read().strip())
        except:
            pass
    
    # Fallback: search for process
    import subprocess
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
    try:
        with open("/tmp/voice_typer_status", "r") as f:
            return f.read().strip()
    except:
        return "ON"  # Default

class VoiceTyperToggle:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VoiceTyper")
        self.root.geometry("120x50")
        self.root.resizable(False, False)
        
        # Keep window on top
        self.root.attributes('-topmost', True)
        
        # Position in bottom-left corner
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"120x50+20+{screen_height - 100}")
        
        # Main button
        self.button = tk.Button(
            self.root,
            text="Listening: ON",
            font=("Arial", 10, "bold"),
            bg="#4CAF50",
            fg="white",
            relief=tk.FLAT,
            command=self.toggle
        )
        self.button.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Update status periodically
        self.update_status()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def toggle(self):
        """Toggle listening state."""
        pid = get_voice_typer_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGUSR1)
                # Status will update on next check
            except Exception as e:
                print(f"Error toggling: {e}")
        else:
            self.button.config(
                text="Not Running",
                bg="#9E9E9E"
            )
    
    def update_status(self):
        """Update button based on current status."""
        status = get_status()
        pid = get_voice_typer_pid()
        
        if not pid:
            self.button.config(
                text="Not Running",
                bg="#9E9E9E"
            )
        elif status == "ON":
            self.button.config(
                text="Listening: ON",
                bg="#4CAF50"  # Green
            )
        else:
            self.button.config(
                text="Listening: OFF",
                bg="#F44336"  # Red
            )
        
        # Check again in 500ms
        self.root.after(500, self.update_status)
    
    def on_close(self):
        """Minimize to tray or just hide."""
        self.root.destroy()
    
    def run(self):
        self.root.mainloop()

def main():
    toggle = VoiceTyperToggle()
    toggle.run()

if __name__ == "__main__":
    main()
