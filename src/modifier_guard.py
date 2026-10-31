"""Wait for the user to let go of modifier keys before injecting keystrokes.

Injected keys must never release or re-press a modifier the user is holding.
`xdotool --clearmodifiers` does exactly that: it sends a fake release for every
held modifier, types, then presses them again on the XTEST device. The fake
release ends an Alt push-to-talk mid-hold, and the re-press can leave Super or
Alt logically held after the real key comes up (so C opens the calendar).
Instead, wait here until no modifier is down, then inject plain keys.
"""
import time

from .utils.logger import logger

DEFAULT_TIMEOUT_S = 30.0
POLL_S = 0.02


def held_modifiers(display) -> list:
    """Keycodes of modifier keys currently down, per the X server's key map."""
    modifier_codes = {code for row in display.get_modifier_mapping() for code in row if code}
    keymap = display.query_keymap()
    return sorted(code for code in modifier_codes if keymap[code // 8] >> (code % 8) & 1)


def wait_for_modifiers_released(timeout_s: float = DEFAULT_TIMEOUT_S, poll_s: float = POLL_S) -> bool:
    """Block until no modifier key is held.

    Returns True once the keyboard is free (or when the X display cannot be
    opened, so typing is never blocked by a missing display), False if a
    modifier is still held after timeout_s. Callers must not type on False:
    injecting while Alt or Ctrl is down fires shortcuts instead of text.
    """
    try:
        from Xlib import display as xdisplay
        display = xdisplay.Display()
    except Exception as exc:
        logger.warning(f"Modifier guard unavailable ({exc}); typing without waiting")
        return True
    try:
        deadline = time.monotonic() + timeout_s
        announced = False
        while True:
            held = held_modifiers(display)
            if not held:
                return True
            if not announced:
                logger.info(f"Waiting for held modifier keys {held} to be released before typing")
                announced = True
            if time.monotonic() >= deadline:
                logger.warning(f"Modifier keys {held} still held after {timeout_s:.0f}s; not typing")
                return False
            time.sleep(poll_s)
    finally:
        display.close()
