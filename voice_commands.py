"""Voice command processing for VoiceTyper."""
import re
from typing import Callable, Dict, Optional
from enum import Enum, auto
import logging


class VoiceCommand(Enum):
    """Available voice commands."""
    STOP_LISTENING = auto()
    START_LISTENING = auto()
    TOGGLE_MODE = auto()
    CLEAR_LAST = auto()
    UNDO = auto()
    HELP = auto()
    EXPORT = auto()


class VoiceCommandProcessor:
    """Processes voice commands from transcripts."""
    
    # Command patterns - maps phrases to commands
    COMMAND_PATTERNS = {
        VoiceCommand.STOP_LISTENING: [
            r'stop listening',
            r'stop typing',
            r'pause transcription',
            r'go to sleep',
            r'shut down',
        ],
        VoiceCommand.START_LISTENING: [
            r'start listening',
            r'start typing',
            r'resume transcription',
            r'wake up',
            r'begin typing',
        ],
        VoiceCommand.TOGGLE_MODE: [
            r'toggle mode',
            r'switch mode',
            r'change mode',
        ],
        VoiceCommand.CLEAR_LAST: [
            r'clear that',
            r'delete that',
            r'undo that',
            r'scratch that',
            r'remove that',
        ],
        VoiceCommand.UNDO: [
            r'^(undo|undo last)$',
        ],
        VoiceCommand.EXPORT: [
            r'export transcript',
            r'save transcript',
            r'export to file',
        ],
        VoiceCommand.HELP: [
            r'^help$',
            r'what can i say',
            r'voice commands',
            r'show commands',
        ],
    }
    
    def __init__(self, enabled: bool = True, prefix: Optional[str] = "computer",
                 prefixes: Optional[list] = None):
        """
        prefix: single wake word (backward compat).
        prefixes: list of accepted wake phrases (e.g. ["computer", "hey computer",
                  "ok computer"]). If provided, overrides `prefix`.
        """
        self.enabled = enabled
        if prefixes:
            self.prefixes = [p.lower() for p in prefixes]
        elif prefix:
            self.prefixes = [prefix.lower()]
        else:
            self.prefixes = []
        self.prefix = self.prefixes[0] if self.prefixes else None
        self.handlers: Dict[VoiceCommand, Callable] = {}
        self.last_command: Optional[VoiceCommand] = None
        
    def register_handler(self, command: VoiceCommand, handler: Callable) -> None:
        """Register a handler for a command."""
        self.handlers[command] = handler
    
    def process(self, transcript: str) -> Optional[VoiceCommand]:
        """Process a transcript for commands.
        
        Returns the command if found and handled, None otherwise.
        """
        if not self.enabled or not transcript:
            return None
        if not isinstance(transcript, str):
            return None

        text = transcript.lower().strip().rstrip(".,!?")

        # Check for any accepted wake phrase
        if self.prefixes:
            matched_prefix = None
            for p in self.prefixes:
                if text.startswith(p + " "):
                    matched_prefix = p
                    break
                if text == p:
                    return None  # just said wake phrase, waiting for command
            if not matched_prefix:
                return None
            text = text[len(matched_prefix) + 1:].strip()

        for command, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logging.info(f"Voice command detected: {command.name}")
                    self.last_command = command
                    handled = self._execute_handler(command)
                    if not handled:
                        logging.warning(f"Voice command {command.name} had no handler or handler failed")
                    return command

        return None
    
    def _execute_handler(self, command: VoiceCommand) -> bool:
        """Execute handler for a command."""
        if command in self.handlers:
            try:
                self.handlers[command]()
                return True
            except Exception as e:
                logging.error(f"Error executing command {command}: {e}")
        return False
    
    def get_help_text(self) -> str:
        """Get help text for available commands."""
        lines = ["🎤 Voice Commands:"]
        lines.append(f"  (Prefix with '{self.prefix}' if configured)\n")
        
        sep = '" or "'
        for command, patterns in self.COMMAND_PATTERNS.items():
            examples = patterns[:2]  # Show first 2 examples
            examples_clean = [e.replace(r'\b', '').replace(r'^', '').replace(r'$', '') for e in examples]
            joined = sep.join(examples_clean)
            name_title = command.name.replace('_', ' ').title()
            lines.append(f"  • {name_title}")
            lines.append(f'    Say: "{joined}"')
        
        return '\n'.join(lines)
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable voice commands."""
        self.enabled = enabled
        logging.info(f"Voice commands {'enabled' if enabled else 'disabled'}")
