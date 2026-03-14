"""Voice command processing for VoiceTyper.

Allows voice control of the application itself.
"""

import re
from typing import Callable, Dict, Optional
from enum import Enum, auto


class VoiceCommand(Enum):
    """Available voice commands."""
    STOP_LISTENING = auto()
    START_LISTENING = auto()
    TOGGLE_MODE = auto()
    CLEAR_LAST = auto()
    UNDO = auto()
    HELP = auto()


class VoiceCommandProcessor:
    """Processes voice commands from transcripts."""
    
    # Command patterns - maps phrases to commands
    COMMAND_PATTERNS = {
        VoiceCommand.STOP_LISTENING: [
            r'stop listening',
            r'stop typing',
            r'pause transcription',
            r'go to sleep',
        ],
        VoiceCommand.START_LISTENING: [
            r'start listening',
            r'start typing',
            r'resume transcription',
            r'wake up',
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
        ],
        VoiceCommand.UNDO: [
            r'undo',
            r'undo last',
        ],
        VoiceCommand.HELP: [
            r'help',
            r'what can i say',
            r'voice commands',
        ],
    }
    
    def __init__(self):
        self.handlers: Dict[VoiceCommand, Callable] = {}
        self.enabled = True
        self.command_prefix = "computer"
        
    def register_handler(self, command: VoiceCommand, handler: Callable) -> None:
        """Register a handler for a command."""
        self.handlers[command] = handler
    
    def process(self, transcript: str) -> Optional[VoiceCommand]:
        """Process a transcript for commands.
        
        Returns the command if found, None otherwise.
        """
        if not self.enabled:
            return None
            
        text = transcript.lower().strip()
        
        # Check for command prefix (optional)
        has_prefix = text.startswith(self.command_prefix)
        if has_prefix:
            text = text[len(self.command_prefix):].strip()
        
        for command, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    self._execute_handler(command)
                    return command
        
        return None
    
    def _execute_handler(self, command: VoiceCommand) -> None:
        """Execute handler for a command."""
        if command in self.handlers:
            try:
                self.handlers[command]()
            except Exception as e:
                print(f"Error executing command {command}: {e}")
    
    def get_help_text(self) -> str:
        """Get help text for available commands."""
        lines = ["Voice Commands:"]
        for command, patterns in self.COMMAND_PATTERNS.items():
            examples = patterns[:2]  # Show first 2 examples
            lines.append(f"  {command.name}: {', '.join(examples)}")
        return '\n'.join(lines)
