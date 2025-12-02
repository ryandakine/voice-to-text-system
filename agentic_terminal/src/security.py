import re
from typing import Optional

class SafetyException(Exception):
    """Exception raised when a command violates security policies."""
    pass

class SecurityManager:
    # Regex patterns for dangerous commands
    BLACKLIST_PATTERNS = [
        r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+|-[a-zA-Z]*f[a-zA-Z]*\s+).*\/",  # rm -rf /... (rough check)
        r"rm\s+-rf\s+.*", # Catch generic rm -rf
        r"mkfs",          # Formatting filesystems
        r"dd\s+if=",      # Direct disk writing
        r"chmod\s+(-R\s+)?777", # Wide open permissions
        r":\(\)\{ :\|:& \};:", # Fork bomb
        r">\s*/dev/sd[a-z]", # Overwriting raw devices
    ]

    @staticmethod
    def check_command(command: str) -> None:
        """
        Check if a command matches any blacklist patterns.
        Raises SafetyException if a match is found.
        """
        for pattern in SecurityManager.BLACKLIST_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                raise SafetyException(f"Command blocked by security policy: matches pattern '{pattern}'")

    @staticmethod
    def prompt_confirmation(command: str) -> bool:
        """
        In a real TUI, this would interact with the user.
        For now, we rely on the main loop to handle the exception and prompt.
        """
        # This method is a placeholder if we wanted logic here, 
        # but the spec says "raise a custom SafetyException that requires explicit user confirmation in the UI."
        # So the UI handles the confirmation.
        pass
