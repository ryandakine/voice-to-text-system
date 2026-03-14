from typing import Protocol, Optional, Dict, Any

class TranscriptionService(Protocol):
    """Protocol for speech-to-text transcription services."""
    
    def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Transcribe audio file to text."""
        ...

    def load_model(self, model_name: Optional[str] = None) -> bool:
        """Load the transcription model."""
        ...

class OutputService(Protocol):
    """Protocol for text output/insertion services."""
    
    def insert_text(self, text: str, window_id: Optional[str] = None) -> bool:
        """Insert text into the active application.

        window_id: X11 window ID to focus before pasting (optional). When
        provided the inserter will restore focus to that window, which
        compensates for GTK/Electron menu bars stealing focus on Alt-release.
        """
        ...
