"""Exercise real X11 input in a private display, never the user's desktop."""
import json
import subprocess
import threading
import time
import tkinter as tk
from queue import Queue

import os
import sys
from pathlib import Path

# Always run in a private display so synthetic input cannot reach the desktop.
if os.environ.get("VOICE_INSERTION_PRIVATE_DISPLAY") != "1":
    import subprocess
    raise SystemExit(subprocess.run([
        "xvfb-run", "-a", "env", "VOICE_INSERTION_PRIVATE_DISPLAY=1",
        sys.executable, str(Path(__file__).resolve()),
    ]).returncode)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text_insertion import TextInserter

root = tk.Tk()
root.title("Voice insertion diagnostic")
menu = tk.Menu(root)
file_menu = tk.Menu(menu, tearoff=False)
file_menu.add_command(label="New")
menu.add_cascade(label="File", underline=0, menu=file_menu)
root.config(menu=menu)
entry = tk.Entry(root, width=60)
entry.pack(padx=20, pady=20)
events = Queue()
results = []
expected = "Voice typing works. "


def worker():
    wm = subprocess.Popen(
        ["metacity", "--sm-disable"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        time.sleep(0.5)
        inserter = TextInserter()
        for method in ["keyboard", "clipboard", "xdotool"]:
            events.put(("prepare", None))
            time.sleep(0.2)
            subprocess.run(["xdotool", "key", "alt+f"], check=True, capture_output=True)
            time.sleep(0.2)
            inserter.primary_method = method
            inserter.fallback_method = method
            success = inserter.insert_text(expected)
            events.put(("check", {"method": method, "reported_success": success}))
            time.sleep(0.2)
            subprocess.run(["xdotool", "key", "Escape"], capture_output=True)
        events.put(("done", None))
    except Exception as exc:
        events.put(("error", str(exc)))
    finally:
        wm.terminate()


def poll():
    while not events.empty():
        action, data = events.get()
        if action == "prepare":
            entry.delete(0, tk.END)
            entry.focus_force()
        elif action == "check":
            data.update(actual_text=entry.get(), expected=expected)
            results.append(data)
        elif action == "done":
            print(json.dumps(results), flush=True)
            root.destroy()
            return
        elif action == "error":
            print(json.dumps({"error": data}), flush=True)
            root.destroy()
            return
    root.after(20, poll)


root.after(100, lambda: threading.Thread(target=worker, daemon=True).start())
root.after(20, poll)
root.after(15000, root.destroy)
root.mainloop()

assert len(results) == 3 and all(
    r["reported_success"] and r["actual_text"] == r["expected"] for r in results
), "Text did not reach the field intact; see the results above."
