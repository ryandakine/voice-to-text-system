#!/usr/bin/env python3
"""Stuck-key watcher for the X11 session.

Polls each keyboard device's key state once a second and tells you when a
modifier key is stuck down:

- A modifier held >= XTEST_RELEASE_AFTER_S on the "Virtual core XTEST keyboard"
  is a fake key left down by an input-injection tool (xdotool --clearmodifiers,
  pynput, the voice typer). Fake keys are never held on purpose, so the watcher
  releases it on that same XTEST device and shows a notification.

  Caveat: x11vnc and RustDesk inject the remote user's real keystrokes through
  that same XTEST device, so a remote user legitimately holds Shift or Ctrl on
  it. The release waits 12 seconds, and is skipped entirely while a remote
  session is established on TCP port 5900 (x11vnc's port).
- Super/Ctrl/Shift held >= PHYSICAL_WARN_AFTER_S on a real keyboard gets a
  warning only (software cannot release another device's key; unplugging the
  receiver or logging out does). Alt is skipped there because push-to-talk
  holds it for long stretches on purpose.

Every event is appended to ~/.local/state/stuck-keys.log.
"""
import fcntl
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

POLL_S = 1.0
XTEST_RELEASE_AFTER_S = 12.0
PHYSICAL_WARN_AFTER_S = 20.0
XTEST_NAME = "Virtual core XTEST keyboard"
LOG_PATH = Path.home() / ".local/state/stuck-keys.log"
LOCK_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "stuck-key-watch.lock"

# X keycodes on this keymap (evdev): see `xmodmap -pm`.
MODIFIERS = {
    50: "Shift_L", 62: "Shift_R", 37: "Control_L", 105: "Control_R",
    64: "Alt_L", 108: "Alt_R", 133: "Super_L", 134: "Super_R",
    204: "Alt_L(alt)", 205: "Meta_L", 206: "Super_L(alt)", 207: "Hyper_L",
}
PHYSICAL_WARN_KEYS = {50, 62, 37, 105, 133, 134}
NOT_KEYBOARDS = ("Power Button", "Sleep Button", "XTEST")

_DEVICE_LINE = re.compile(r"↳\s*(.+?)\s+id=(\d+)\s+\[slave\s+keyboard")
_KEY_DOWN = re.compile(r"key\[(\d+)\]=down")


def parse_keyboards(xinput_list: str) -> dict:
    """Map device id -> name for every slave keyboard in `xinput list` output."""
    found = {}
    for line in xinput_list.splitlines():
        m = _DEVICE_LINE.search(line)
        if m:
            found[int(m.group(2))] = m.group(1).strip()
    return found


def parse_down_keys(query_state: str) -> set:
    """Keycodes reported down by `xinput query-state <id>`."""
    return {int(k) for k in _KEY_DOWN.findall(query_state)}


class Tracker:
    """Remembers since when each (device, keycode) has been continuously down."""

    def __init__(self):
        self.since = {}
        self.acted = set()

    def update(self, device_id: int, down: set, now: float) -> None:
        for key in list(self.since):
            if key[0] == device_id and key[1] not in down:
                del self.since[key]
                self.acted.discard(key)
        for code in down:
            self.since.setdefault((device_id, code), now)

    def held_for(self, device_id: int, code: int, now: float) -> float:
        start = self.since.get((device_id, code))
        return 0.0 if start is None else now - start


def decide(tracker: Tracker, devices: dict, xtest_id, now: float) -> list:
    """Return actions: ("release", dev, code) for stuck fake keys, ("warn", dev, code) for real ones."""
    actions = []
    for (dev, code), _start in list(tracker.since.items()):
        if code not in MODIFIERS or (dev, code) in tracker.acted:
            continue
        held = now - _start
        if dev == xtest_id and held >= XTEST_RELEASE_AFTER_S:
            actions.append(("release", dev, code))
        elif dev != xtest_id and code in PHYSICAL_WARN_KEYS and held >= PHYSICAL_WARN_AFTER_S:
            actions.append(("warn", dev, code))
    return actions


def log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def notify(title: str, body: str) -> None:
    try:
        subprocess.run(["notify-send", "-u", "critical", "-i", "input-keyboard", title, body],
                       timeout=5, check=False)
    except Exception:
        pass


def remote_session_active() -> bool:
    """True when something has an established session on TCP port 5900 (x11vnc).

    x11vnc and RustDesk deliver the remote user's keystrokes through the XTEST
    device, so a held Shift/Ctrl there is the remote user, not a stuck fake key.
    """
    try:
        out = subprocess.run(
            ["ss", "-Htn", "state", "established", "( sport = :5900 )"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return False  # cannot tell; a crashed watcher would protect nobody
    return bool(out.strip())


def release_xtest_key(code: int) -> None:
    """Send a key release for `code` on the XTEST device (the one holding it)."""
    from Xlib import X, display
    from Xlib.ext import xtest
    d = display.Display()
    try:
        xtest.fake_input(d, X.KeyRelease, code)
        d.sync()
    finally:
        d.close()


def run(once: bool = False, stop_event: "threading.Event | None" = None) -> None:
    tracker = Tracker()
    skipped = set()
    devices, xtest_id, refreshed = {}, None, 0.0
    while True:
        now = time.monotonic()
        if now - refreshed > 10 or not devices:
            out = subprocess.run(["xinput", "list"], capture_output=True, text=True).stdout
            devices = parse_keyboards(out)
            xtest_id = next((i for i, n in devices.items() if n == XTEST_NAME), None)
            refreshed = now
        for dev, name in devices.items():
            if dev != xtest_id and any(s in name for s in NOT_KEYBOARDS):
                continue
            state = subprocess.run(["xinput", "query-state", str(dev)],
                                   capture_output=True, text=True).stdout
            tracker.update(dev, parse_down_keys(state), now)
        for kind, dev, code in decide(tracker, devices, xtest_id, now):
            key = MODIFIERS[code]
            if kind == "release" and remote_session_active():
                # Not marked acted: once the remote session ends, a key still held is released.
                if (dev, code) not in skipped:
                    skipped.add((dev, code))
                    log(f"skipped: remote session active ({key} held on '{devices.get(dev)}')")
                continue
            skipped.discard((dev, code))
            tracker.acted.add((dev, code))
            if kind == "release":
                release_xtest_key(code)
                log(f"RELEASED fake {key} (keycode {code}) held {tracker.held_for(dev, code, now):.0f}s "
                    f"on '{devices.get(dev)}'")
                notify("Keyboard was stuck - fixed",
                       f"A fake {key} key was being held down by a typing tool (voice typer / xdotool). "
                       f"It has been released.")
            else:
                log(f"WARN real {key} (keycode {code}) down {tracker.held_for(dev, code, now):.0f}s "
                    f"on '{devices.get(dev)}'")
                notify("Keyboard may be stuck",
                       f"{key} has been held down for {PHYSICAL_WARN_AFTER_S:.0f}+ seconds on "
                       f"{devices.get(dev)}. If you are not holding it, unplug and replug the "
                       f"keyboard's receiver, or log out and back in.")
        if once or (stop_event is not None and stop_event.is_set()):
            return
        time.sleep(POLL_S)


def main() -> int:
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("stuck_key_watch: already running", file=sys.stderr)
        return 0
    log("watcher started")
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
