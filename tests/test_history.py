"""Tests for transcript history I/O hardening (PR #4 Grok fixes)."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from history import TranscriptHistory


class TestHistoryWriteSoftFail:
    """Grok #1: file I/O errors must not crash dictation."""

    def test_history_writes_skip_on_permission_error(self, tmp_path, caplog):
        """A PermissionError on append is logged and swallowed."""
        h = TranscriptHistory(history_dir=str(tmp_path))

        with caplog.at_level(logging.WARNING, logger="history"):
            with patch("history.open", side_effect=PermissionError("nope")):
                # add() must not raise; dictation continues.
                h.add("hello world")

        assert any("Could not append" in r.message for r in caplog.records)
        # Entry still in memory so get_recent/search keep working this session.
        assert len(h.current_session) == 1
        assert h.current_session[0].text == "hello world"

    def test_history_writes_skip_on_oserror(self, tmp_path, caplog):
        """A generic OSError (disk full, read-only) is also swallowed."""
        h = TranscriptHistory(history_dir=str(tmp_path))

        with caplog.at_level(logging.WARNING, logger="history"):
            with patch("history.open", side_effect=OSError("ENOSPC")):
                h.add("disk full test")

        assert any("Could not append" in r.message for r in caplog.records)
        assert len(h.current_session) == 1

    def test_history_init_survives_unwritable_dir(self, tmp_path, caplog):
        """mkdir failure on init does not raise; writes become no-ops."""
        target = tmp_path / "wont_create"
        with caplog.at_level(logging.WARNING, logger="history"):
            with patch.object(Path, "mkdir", side_effect=PermissionError("no")):
                h = TranscriptHistory(history_dir=str(target))

        assert h._history_dir_ok is False
        # add() still works as in-memory store.
        h.add("offline mode")
        assert len(h.current_session) == 1


class TestHistoryDurability:
    """Grok #2: per-utterance writes mean crash-loss is one utterance, not all."""

    def test_each_utterance_is_persisted_immediately(self, tmp_path):
        h = TranscriptHistory(history_dir=str(tmp_path))
        h.add("first")
        h.add("second")
        h.add("third")

        daily = h._daily_file()
        assert daily.exists()
        lines = daily.read_text().strip().splitlines()
        assert len(lines) == 3
        texts = [json.loads(line)["text"] for line in lines]
        assert texts == ["first", "second", "third"]

    def test_simulated_crash_after_two_utterances_preserves_them(self, tmp_path):
        """No explicit flush call — file should already have the data."""
        h = TranscriptHistory(history_dir=str(tmp_path))
        h.add("survives crash")
        h.add("also survives")
        # Simulate hard crash: drop the object without calling save_session.
        del h

        daily = next(tmp_path.glob("history-*.jsonl"))
        lines = daily.read_text().strip().splitlines()
        assert len(lines) == 2


class TestHistoryRotation:
    """Grok #3: daily-file naming + retention pruning."""

    def test_history_rotation_prunes_old_files(self, tmp_path):
        # Seed with files spanning 60 days back, today.
        today = datetime.now().date()
        seeded = []
        for days_back in (0, 1, 15, 29, 30, 31, 60):
            d = today - timedelta(days=days_back)
            f = tmp_path / f"history-{d.strftime('%Y-%m-%d')}.jsonl"
            f.write_text('{"text":"x","timestamp":"2026-01-01T00:00:00"}\n')
            seeded.append((days_back, f))

        # Default retention is 30 days; instantiate triggers _prune_old_files.
        TranscriptHistory(history_dir=str(tmp_path))

        for days_back, f in seeded:
            if days_back <= 30:
                assert f.exists(), f"{days_back}-day-old file should survive"
            else:
                assert not f.exists(), f"{days_back}-day-old file should be pruned"

    def test_retention_zero_disables_pruning(self, tmp_path):
        old = tmp_path / "history-2020-01-01.jsonl"
        old.write_text("{}\n")
        TranscriptHistory(history_dir=str(tmp_path), retention_days=0)
        assert old.exists()

    def test_non_history_files_are_left_alone(self, tmp_path):
        unrelated = tmp_path / "history-not-a-date.jsonl"
        unrelated.write_text("{}\n")
        random = tmp_path / "session_20200101_120000.json"
        random.write_text("[]")
        TranscriptHistory(history_dir=str(tmp_path))
        # Glob pattern matches `history-*.jsonl`; the first survives the
        # date-parse skip, the second isn't matched by the glob at all.
        assert unrelated.exists()
        assert random.exists()
