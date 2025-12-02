import os
from typing import List, Optional, Dict, Any

class SessionState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionState, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.cwd: str = os.getcwd()
        self.sudo_password: Optional[str] = None
        self.history: List[Dict[str, Any]] = []
        self.total_cost: float = 0.0
        self._initialized = True

    def update_cwd(self, new_path: str):
        """Update the current working directory, resolving absolute paths."""
        if os.path.isabs(new_path):
            self.cwd = new_path
        else:
            self.cwd = os.path.abspath(os.path.join(self.cwd, new_path))

    def add_message(self, role: str, content: str, tool_calls: Optional[List] = None, tool_call_id: Optional[str] = None, name: Optional[str] = None):
        """Add a message to the conversation history."""
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if tool_call_id:
            message["tool_call_id"] = tool_call_id
        if name:
            message["name"] = name
        
        self.history.append(message)

    def add_cost(self, cost: float):
        """Add to the running total cost."""
        self.total_cost += cost

    def clear_sudo_password(self):
        """Clear the cached sudo password."""
        self.sudo_password = None

    def set_sudo_password(self, password: str):
        """Set the sudo password in memory."""
        self.sudo_password = password
