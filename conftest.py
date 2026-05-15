"""Root-level pytest conftest.

Stubs heavy runtime dependencies (pyaudio, faster_whisper, silero_vad, pynput)
so the test suite runs on minimal CI images that only have pytest + numpy.
Real-environment tests still install these via requirements.txt.
"""

import sys
from unittest.mock import MagicMock


def _stub(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()


_stub("pyaudio")
_stub("pynput")
_stub("pynput.keyboard")
_stub("pyautogui")
_stub("pyperclip")
_stub("whisper")
_stub("silero_vad")

# GTK stubs — overlay imports them at module level, tests never render a window.
if "gi" not in sys.modules:
    gi = MagicMock()
    gi.require_version = MagicMock()
    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = MagicMock()

# faster_whisper needs to expose WhisperModel as an attribute of the module.
if "faster_whisper" not in sys.modules:
    fw = MagicMock()
    fw.WhisperModel = MagicMock()
    sys.modules["faster_whisper"] = fw
