"""Real X server checks for why push-to-talk got cut off and keys got stuck.

Intent: while Ryan holds Alt to talk, nothing the voice typer injects may make
the key listener see Alt released. The old `xdotool --clearmodifiers` did
(cutting the recording off mid-sentence); the fix waits for the user to let go
of every modifier, then injects plain keys.

The pynput listener runs in a subprocess so the MagicMock stubs other test
files install for pynput/pyautogui are not disturbed.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = ":93"
ALT_L = 64

LISTENER = """
import sys, time
from pynput import keyboard
out = open(sys.argv[1], "w", buffering=1)
def press(k):
    if k in (keyboard.Key.alt, keyboard.Key.alt_l): out.write("press\\n")
def release(k):
    if k in (keyboard.Key.alt, keyboard.Key.alt_l): out.write("release\\n")
with keyboard.Listener(on_press=press, on_release=release):
    out.write("ready\\n")
    time.sleep(float(sys.argv[2]))
"""

pytestmark = pytest.mark.skipif(
    not (shutil.which("Xvfb") and shutil.which("xdotool")), reason="needs Xvfb and xdotool")


@pytest.fixture
def x_server(monkeypatch):
    # -noreset: a real desktop never resets, so state set by one client persists.
    xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-noreset", "-screen", "0", "640x480x24"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    monkeypatch.setenv("DISPLAY", DISPLAY)
    try:
        yield
    finally:
        xvfb.terminate()
        xvfb.wait(timeout=5)


def _hold_alt():
    """A separate X client (the 'user') presses Alt and keeps holding it."""
    from Xlib import X, display
    from Xlib.ext import xtest
    user = display.Display(DISPLAY)
    xtest.fake_input(user, X.KeyPress, ALT_L)
    user.sync()
    return user


def _let_go(user):
    from Xlib import X
    from Xlib.ext import xtest
    xtest.fake_input(user, X.KeyRelease, ALT_L)
    user.sync()


def _alt_events_during(tmp_path, action) -> list:
    """Run `action` while Alt is held; return the Alt events a pynput listener saw."""
    log = tmp_path / "alt-events.txt"
    listener = subprocess.Popen([sys.executable, "-c", LISTENER, str(log), "3"],
                                env={**os.environ, "DISPLAY": DISPLAY})
    deadline = time.time() + 5
    while time.time() < deadline and not (log.exists() and "ready" in log.read_text()):
        time.sleep(0.05)
    user = _hold_alt()
    time.sleep(0.3)
    action()
    time.sleep(0.3)
    seen_while_held = [l for l in log.read_text().split() if l != "ready"]
    _let_go(user)
    user.close()
    listener.terminate()
    listener.wait(timeout=5)
    return seen_while_held


def test_guard_waits_while_alt_is_held_and_continues_once_released(x_server):
    sys.path.insert(0, str(ROOT))
    from src.modifier_guard import wait_for_modifiers_released

    user = _hold_alt()
    result = {}
    worker = threading.Thread(target=lambda: result.setdefault("free", wait_for_modifiers_released(timeout_s=5)))
    worker.start()
    time.sleep(0.5)
    assert worker.is_alive(), "typing would have started while Alt was still held"
    _let_go(user)
    worker.join(timeout=1)
    user.close()
    assert not worker.is_alive() and result["free"] is True


def test_old_clearmodifiers_fakes_an_alt_release_mid_hold(x_server, tmp_path):
    """The bug: this is exactly what cut push-to-talk off while Alt was still down."""
    seen = _alt_events_during(tmp_path, lambda: subprocess.run(
        ["xdotool", "key", "--clearmodifiers", "Escape"], check=True))
    assert "release" in seen, seen


def test_plain_escape_leaves_a_held_alt_alone(x_server, tmp_path):
    seen = _alt_events_during(tmp_path, lambda: subprocess.run(
        ["xdotool", "key", "Escape"], check=True))
    assert "release" not in seen, seen
