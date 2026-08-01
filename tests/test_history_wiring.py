"""History capture wiring for the live whisper typer.

Covers the config-gated init helper AND the _transcribe_and_type hook itself —
the hook tests drive the real method, so removing the wiring fails them.
"""
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from history_manager import HistoryManager
from voice_typer_whisper import _init_history

# 1s of 16 kHz int16 at high amplitude — defeats the silent-capture guard
LOUD_1S = b"\x00\x30" * 16000


def _make_app(history):
    import voice_typer_whisper as vtw
    with patch.object(vtw, "WhisperTranscriber"), \
         patch.object(vtw, "SileroVAD"), \
         patch.object(vtw.keyboard, "Listener"), \
         patch.object(vtw, "signal"), \
         patch.object(vtw, "_init_history", return_value=history):
        return vtw.VoiceTyperWhisper()


# ---------- _init_history helper ----------

def test_enabled_config_returns_working_manager(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    db = tmp_path / "history.db"
    cfg.write_text(json.dumps(
        {"history": {"enabled": True, "db_path": str(db), "retention_days": 90}}
    ))

    hm = _init_history(str(cfg))

    assert hm is not None
    hm.add("test one two", duration_ms=1500)
    rows = sqlite3.connect(db).execute(
        "SELECT text, duration_ms FROM transcripts"
    ).fetchall()
    assert rows == [("test one two", 1500)]


def test_disabled_config_returns_none(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"history": {"enabled": False}}))

    assert _init_history(str(cfg)) is None


def test_unreadable_config_never_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json")

    assert _init_history(str(cfg)) is None


# ---------- the actual hook in _transcribe_and_type ----------

def test_typed_utterance_is_persisted() -> None:
    hist = MagicMock()
    app = _make_app(hist)
    app._transcriber.transcribe = MagicMock(return_value="hello world")
    app._type_text = MagicMock(return_value=True)

    app._transcribe_and_type(LOUD_1S, is_ptt=True)

    hist.add.assert_called_once_with("hello world", duration_ms=1000)


def test_voice_command_is_not_persisted() -> None:
    hist = MagicMock()
    app = _make_app(hist)
    app._transcriber.transcribe = MagicMock(return_value="computer stop listening")
    app._type_text = MagicMock(return_value=True)

    app._transcribe_and_type(LOUD_1S, is_ptt=True)

    hist.add.assert_not_called()
    app._type_text.assert_not_called()


def test_listening_off_drop_is_not_persisted() -> None:
    hist = MagicMock()
    app = _make_app(hist)
    app._transcriber.transcribe = MagicMock(return_value="ambient chatter")
    app._type_text = MagicMock(return_value=True)

    # listening flag is OFF by default and is_ptt=False → must drop silently
    app._transcribe_and_type(LOUD_1S, is_ptt=False)

    hist.add.assert_not_called()
    app._type_text.assert_not_called()


def test_failed_typing_is_not_persisted() -> None:
    hist = MagicMock()
    app = _make_app(hist)
    app._transcriber.transcribe = MagicMock(return_value="hello world")
    app._type_text = MagicMock(return_value=False)

    app._transcribe_and_type(LOUD_1S, is_ptt=True)

    hist.add.assert_not_called()
    assert app._last_typed_text is None


def test_clear_last_retracts_history() -> None:
    hist = MagicMock()
    app = _make_app(hist)

    with patch("voice_typer_whisper.subprocess.run"):
        app._handle_clear_last()

    hist.delete_last.assert_called_once()


# ---------- HistoryManager additions ----------

def test_delete_last_removes_only_latest_own_row(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    hm = HistoryManager(db_path=str(db))
    hm.add("first")
    hm.add("second")

    hm.delete_last()

    texts = [r[0] for r in sqlite3.connect(db).execute(
        "SELECT text FROM transcripts ORDER BY id"
    )]
    assert texts == ["first"]


def test_db_file_is_owner_only(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    HistoryManager(db_path=str(db))

    assert (db.stat().st_mode & 0o777) == 0o600
