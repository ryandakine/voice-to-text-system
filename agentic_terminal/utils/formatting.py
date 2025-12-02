from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.spinner import Spinner

console = Console()

def print_user_message(content: str):
    console.print(Panel(content, title="User", border_style="blue"))

def print_agent_message(content: str):
    console.print(Panel(Markdown(content), title="Agent", border_style="green"))

def print_tool_execution(command: str):
    console.print(Text(f"Executing: {command}", style="dim"))

def print_tool_output(output: str):
    if len(output) > 500:
        output = output[:500] + "... (truncated)"
    console.print(Panel(output, title="Tool Output", border_style="dim", expand=False))

def print_error(message: str):
    console.print(Panel(message, title="Error", border_style="red"))

def print_cost(cost: float, total_cost: float):
    console.print(Text(f"Cost: ${cost:.6f} | Total: ${total_cost:.6f}", style="dim italic", justify="right"))

def print_system_message(message: str):
    console.print(Text(message, style="yellow"))
