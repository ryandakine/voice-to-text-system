"""Embedded GTK3 listening-state overlay for voice_typer_whisper.

Runs in the main process. GTK main loop owns the main thread; audio and
transcription run on worker threads and call into the overlay via
GLib.idle_add for thread safety.

States (from plan review round 2):
  loading      — model downloading/warming; yellow spinner
  idle         — listening but no speech; low-alpha ring
  speech       — active utterance; green pulse at configurable Hz
  transcribing — speech ended, awaiting final text; slow blue pulse
  error        — persistent error; red static + notify-send fallback
  off          — hidden
"""

import logging
import math
import os
import subprocess
import threading
import time
from enum import Enum

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib, Gdk, cairo
    GTK_AVAILABLE = True
except Exception as _exc:
    logging.warning("GTK3 unavailable, overlay will be headless: %s", _exc)
    GTK_AVAILABLE = False


ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class OverlayState(Enum):
    OFF = "off"
    LOADING = "loading"
    IDLE = "idle"
    SPEECH = "speech"
    TRANSCRIBING = "transcribing"
    ERROR = "error"


def _resolve_position(pos: str, width: int, height: int):
    """Translate a named corner to Gtk position hints."""
    # Anchor points: (gravity, x-margin-from-edge, y-margin-from-edge)
    margin = 20
    screen = Gdk.Screen.get_default()
    if screen is None:
        return 0, 0
    sw, sh = screen.get_width(), screen.get_height()
    pos = (pos or "bottom-right").lower()
    if pos == "top-left":
        return margin, margin
    if pos == "top-right":
        return sw - width - margin, margin
    if pos == "bottom-left":
        return margin, sh - height - margin
    return sw - width - margin, sh - height - margin   # bottom-right default


class ListeningOverlay:
    """Thread-safe overlay controller. Call any public method from any thread;
    GTK operations are marshalled via GLib.idle_add."""

    def __init__(self, position: str = "bottom-right", pulse_hz: float = 1.2,
                 size_px: int = 60, audio_cues: bool = True,
                 play_cmd: str = "paplay"):
        self._position = position
        self._pulse_hz = max(0.2, min(5.0, pulse_hz))
        self._size = size_px
        self._audio_cues = audio_cues
        self._play_cmd = play_cmd
        self._state = OverlayState.OFF
        self._partial_text = ""
        self._lock = threading.Lock()
        self._window = None
        self._area = None
        self._label = None
        self._pulse_phase = 0.0
        self._anim_timer_id = None
        self._thread = None

    # ---------- Public API (thread-safe) ----------

    def start(self):
        """Spawn the GTK main loop on its own dedicated thread. Non-blocking."""
        if not GTK_AVAILABLE:
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="overlay-gtk")
        self._thread.start()

    def stop(self):
        if not GTK_AVAILABLE:
            return
        GLib.idle_add(self._on_stop)

    def set_state(self, state: OverlayState):
        """State update. Audio cue fires on transitions per the attention hierarchy."""
        with self._lock:
            if state == self._state:
                return
            prev = self._state
            self._state = state
        self._maybe_play_cue(prev, state)
        if GTK_AVAILABLE:
            GLib.idle_add(self._queue_redraw)

    def show_partial(self, text: str):
        """Display an interim transcript. Used by Change 3 streaming partials."""
        with self._lock:
            self._partial_text = text or ""
        if GTK_AVAILABLE:
            GLib.idle_add(self._queue_redraw)

    def clear_partial(self):
        self.show_partial("")

    def play_cue(self, name: str):
        """Named cue playback: listen_start | listen_end | cmd_ack | error."""
        if not self._audio_cues:
            return
        path = os.path.join(ASSET_DIR, f"{name}.wav")
        if not os.path.isfile(path):
            return
        try:
            subprocess.Popen(
                [self._play_cmd, path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            # paplay not installed — fall back to aplay silently
            try:
                subprocess.Popen(
                    ["aplay", "-q", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    # ---------- Internal (GTK thread only) ----------

    def _run(self):
        try:
            self._build_ui()
            Gtk.main()
        except Exception as exc:
            logging.error("Overlay GTK loop crashed: %s", exc)

    def _build_ui(self):
        win = Gtk.Window(type=Gtk.WindowType.POPUP)
        win.set_decorated(False)
        win.set_keep_above(True)
        win.set_accept_focus(False)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_default_size(self._size + 240, self._size + 40)  # room for partial text
        win.set_app_paintable(True)
        screen = win.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            win.set_visual(visual)

        # Position
        x, y = _resolve_position(self._position, self._size + 240, self._size + 40)
        win.move(x, y)

        area = Gtk.DrawingArea()
        area.set_size_request(self._size + 240, self._size + 40)
        area.connect("draw", self._on_draw)

        win.add(area)
        win.show_all()

        self._window = win
        self._area = area

        # Animation tick — 30 fps for smooth pulsing; cheap.
        self._anim_timer_id = GLib.timeout_add(33, self._tick)

    def _on_stop(self):
        if self._anim_timer_id is not None:
            try:
                GLib.source_remove(self._anim_timer_id)
            except Exception:
                pass
            self._anim_timer_id = None
        if self._window is not None:
            self._window.destroy()
            self._window = None
        try:
            Gtk.main_quit()
        except Exception:
            pass

    def _tick(self):
        self._pulse_phase = (self._pulse_phase + (1.0 / 30.0) * self._pulse_hz) % 1.0
        self._queue_redraw()
        return True  # keep ticking

    def _queue_redraw(self):
        if self._area is not None:
            self._area.queue_draw()

    def _on_draw(self, widget, cr):
        with self._lock:
            state = self._state
            partial = self._partial_text

        # Transparent clear
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(1)  # CAIRO_OPERATOR_SOURCE clear
        cr.paint()
        cr.set_operator(0)  # CAIRO_OPERATOR_OVER restore

        if state == OverlayState.OFF:
            return False

        radius = self._size / 2 - 4
        cx, cy = self._size / 2 + 4, self._size / 2 + 4

        # State-specific drawing
        if state == OverlayState.LOADING:
            self._draw_spinner(cr, cx, cy, radius, (0.95, 0.80, 0.20))  # yellow
            self._draw_text(cr, "Loading model…")
        elif state == OverlayState.IDLE:
            self._draw_ring(cr, cx, cy, radius, (0.3, 0.8, 0.4), alpha=0.35)
        elif state == OverlayState.SPEECH:
            # Pulse radius between 0.7r and 1.0r, fill alpha 0.5-0.9
            pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * 2 * math.pi)
            r = radius * (0.7 + 0.3 * pulse)
            a = 0.5 + 0.4 * pulse
            self._draw_filled(cr, cx, cy, r, (0.2, 0.85, 0.35), alpha=a)
        elif state == OverlayState.TRANSCRIBING:
            # Slower blue pulse
            pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * math.pi)
            a = 0.4 + 0.4 * pulse
            self._draw_filled(cr, cx, cy, radius * 0.85, (0.25, 0.55, 0.95), alpha=a)
            if partial:
                self._draw_text(cr, partial[:60])
        elif state == OverlayState.ERROR:
            self._draw_filled(cr, cx, cy, radius, (0.90, 0.25, 0.25), alpha=0.9)

        if partial and state == OverlayState.SPEECH:
            self._draw_text(cr, partial[:60])

        return False

    def _draw_filled(self, cr, cx, cy, r, rgb, alpha=1.0):
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], alpha)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()

    def _draw_ring(self, cr, cx, cy, r, rgb, alpha=1.0, width=3):
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], alpha)
        cr.set_line_width(width)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()

    def _draw_spinner(self, cr, cx, cy, r, rgb):
        # Simple rotating arc
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], 0.9)
        cr.set_line_width(4)
        start = self._pulse_phase * 2 * math.pi
        cr.arc(cx, cy, r * 0.9, start, start + math.pi * 1.2)
        cr.stroke()

    def _draw_text(self, cr, text: str):
        cr.set_source_rgba(0.95, 0.95, 0.95, 0.95)
        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(12)
        cr.move_to(self._size + 12, self._size / 2 + 8)
        cr.show_text(text)

    # ---------- Audio cue attention hierarchy ----------

    def _maybe_play_cue(self, prev_state: OverlayState, new_state: OverlayState):
        """Play audio cue on state transitions.
        Priority (attention hierarchy): errors > command acks > recording state.
        """
        if not self._audio_cues:
            return
        # Error takes precedence
        if new_state == OverlayState.ERROR:
            self.play_cue("error")
            return
        # Speech start / end
        if prev_state != OverlayState.SPEECH and new_state == OverlayState.SPEECH:
            self.play_cue("listen_start")
        elif prev_state == OverlayState.SPEECH and new_state in (
            OverlayState.IDLE, OverlayState.TRANSCRIBING
        ):
            self.play_cue("listen_end")
