import pytest
import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config file."""
    config_dir = tmp_path / ".config" / "voice-to-text"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.ini"
    return config_file


@pytest.fixture(autouse=True)
def _no_real_history(monkeypatch):
    """VoiceTyperWhisper.__init__ wires HistoryManager from ~/.voice_typer/config.json;
    tests must never read or write the user's real history database."""
    import voice_typer_whisper as vtw
    monkeypatch.setattr(vtw, "_init_history", lambda *a, **k: None)
