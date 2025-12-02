import os
import platform
import getpass
import json
from typing import Generator, Tuple, Any
from openai import OpenAI
from src.config import Config
from src.state import SessionState
from src.tools.system import run_command
from utils.cost import calculate_cost

class Agent:
    def __init__(self):
        self.client = OpenAI(
            base_url=Config.OPENROUTER_BASE_URL,
            api_key=Config.OPENROUTER_API_KEY
        )
        self.state = SessionState()
        self.model = Config.MODEL_NAME

    def _get_system_prompt(self) -> str:
        """Dynamically generate the system prompt."""
        os_info = f"{platform.system()} {platform.release()}"
        user = getpass.getuser()
        shell = os.environ.get('SHELL', '/bin/bash')
        cwd = self.state.cwd
        
        return f"""You are an expert Linux System Administrator running in a persistent terminal session.
You have full control over the system via the 'run_command' tool.

System Context:
- OS: {os_info}
- User: {user}
- Shell: {shell}
- Current Working Directory: {cwd}

Guidelines:
1. Always check the current directory before assuming file locations.
2. Use 'run_command' to execute shell commands.
3. If a command requires sudo, just run it with 'sudo'. The system handles password entry.
4. Be concise in your final responses.
5. You are persistent. State is maintained between turns.
"""

    def _get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Execute a shell command on the system.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The shell command to execute (e.g., 'ls -la', 'git status')."
                            }
                        },
                        "required": ["command"]
                    }
                }
            }
        ]

    def process_request(self, user_input: str) -> Generator[Tuple[str, Any], None, None]:
        """
        Process a user request, yielding events for the UI.
        Events:
        - ("thinking", None)
        - ("tool_call", command)
        - ("tool_output", output)
        - ("response", text)
        - ("cost", float)
        """
        # Add user message to history
        self.state.add_message("user", user_input)
        
        # Prepare messages including system prompt
        messages = [{"role": "system", "content": self._get_system_prompt()}] + self.state.history
        
        keep_going = True
        while keep_going:
            yield ("thinking", None)
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self._get_tools(),
                    tool_choice="auto"
                )
            except Exception as e:
                yield ("error", str(e))
                return

            # Calculate cost
            usage = response.usage
            if usage:
                cost = calculate_cost(usage.prompt_tokens, usage.completion_tokens)
                self.state.add_cost(cost)
                yield ("cost", cost)

            message = response.choices[0].message
            
            # Add assistant message to history (and local messages list)
            # We need to convert the message object to a dict for storage
            msg_dict = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls
            }
            # Clean up None values
            if msg_dict["tool_calls"] is None:
                del msg_dict["tool_calls"]
            if msg_dict["content"] is None:
                msg_dict["content"] = ""
                
            self.state.history.append(msg_dict)
            messages.append(msg_dict)

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "run_command":
                        args = json.loads(tool_call.function.arguments)
                        command = args.get("command")
                        
                        yield ("tool_call", command)
                        
                        # Execute tool
                        output = run_command(command)
                        
                        yield ("tool_output", output)
                        
                        # Add tool result to history
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": "run_command",
                            "content": output
                        }
                        self.state.history.append(tool_msg)
                        messages.append(tool_msg)
            else:
                # Final response
                yield ("response", message.content)
                keep_going = False
