import sys
import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.status import Status

from src.config import Config
from src.agent import Agent
from src.state import SessionState
from utils.formatting import (
    print_user_message,
    print_agent_message,
    print_tool_execution,
    print_tool_output,
    print_error,
    print_cost,
    print_system_message
)

def main():
    # 1. Setup
    try:
        Config.validate()
    except ValueError as e:
        print_error(str(e))
        print_system_message("Please create a .env file based on .env.example")
        sys.exit(1)

    console = Console()
    state = SessionState()
    agent = Agent()
    
    # Prompt toolkit setup
    style = Style.from_dict({
        'prompt': '#ansigreen bold',
    })
    session = PromptSession(style=style)

    print_system_message("Agentic Terminal Initialized. Type 'exit' to quit.")
    print_system_message(f"Model: {Config.MODEL_NAME}")
    print_system_message(f"CWD: {state.cwd}")
    console.print()

    # 2. Main Loop
    while True:
        try:
            # Update prompt with current CWD (shortened)
            cwd_display = state.cwd.replace(os.path.expanduser("~"), "~")
            user_input = session.prompt(f"[{cwd_display}] > ")
            
            if not user_input.strip():
                continue
                
            if user_input.lower() in ('exit', 'quit'):
                print_system_message("Goodbye!")
                break

            print_user_message(user_input)

            # Process request
            current_cost = 0.0
            
            # We use a status spinner for the "thinking" phases
            with console.status("[bold green]Thinking...", spinner="dots") as status:
                for event_type, data in agent.process_request(user_input):
                    if event_type == "thinking":
                        status.update("[bold green]Thinking...")
                    
                    elif event_type == "tool_call":
                        status.stop()
                        print_tool_execution(data)
                        status.start()
                        status.update("[bold green]Running tool...")
                        
                    elif event_type == "tool_output":
                        status.stop()
                        print_tool_output(data)
                        status.start()
                        status.update("[bold green]Thinking...")
                        
                    elif event_type == "response":
                        status.stop()
                        print_agent_message(data)
                        
                    elif event_type == "cost":
                        current_cost = data
                    
                    elif event_type == "error":
                        status.stop()
                        print_error(data)

            # Print cost footer
            print_cost(current_cost, state.total_cost)
            console.print()

        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        except Exception as e:
            print_error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    import os
    main()
