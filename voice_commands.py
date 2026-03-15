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
    
    def __init__(self, enabled: bool = True, prefix: Optional[str] = "computer"):
        self.enabled = enabled
        self.prefix = prefix.lower() if prefix else None
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
            
        text = transcript.lower().strip()
        
        # Check for command prefix (if configured)
        if self.prefix:
            if text.startswith(self.prefix + " "):
                text = text[len(self.prefix) + 1:].strip()
            elif text == self.prefix:
                return None  # Just said prefix, waiting for command
            else:
                return None  # Prefix not found
        
        for command, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    logging.info(f"Voice command detected: {command.name}")
                    self.last_command = command
                    self._execute_handler(command)
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
        
        for command, patterns in self.COMMAND_PATTERNS.items():
            examples = patterns[:2]  # Show first 2 examples
            examples_clean = [e.replace(r'\b', '').replace(r'^', '').replace(r'$', '') for e in examples]
            lines.append(f"  • {command.name.replace('_', ' ').title()}")
            lines.append(f"    Say: \"{', \" or \"'.join(examples_clean)}\"")
        
        return '\n'.join(lines)
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable voice commands."""
        self.enabled = enabled
        logging.info(f"Voice commands {'enabled' if enabled else 'disabled'}")
