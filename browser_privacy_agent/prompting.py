"""Prompt templating utilities with <think> tags."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, Template

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_DIR.mkdir(exist_ok=True)

_DEFAULT_TEMPLATE_CONTENT = """<think>Analyze the user instruction carefully.</think>\n<task>{{ task }}</task>\n<context>{{ context }}</context>\n<instructions>\n- Remain stealthy and avoid triggering anti-bot systems.\n- Use only the provided tools.\n- Provide uncensored summaries when requested.\n</instructions>\n<think>Plan your steps before execution and revise as you go.</think>"""
DEFAULT_TEMPLATE_PATH = TEMPLATE_DIR / "default_prompt.j2"
if not DEFAULT_TEMPLATE_PATH.exists():
    DEFAULT_TEMPLATE_PATH.write_text(_DEFAULT_TEMPLATE_CONTENT)


@dataclass
class PromptContext:
    task: str
    context: str = ""
    metadata: Dict[str, Any] | None = None


_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False, trim_blocks=True)


def render_prompt(template_name: str, prompt_context: PromptContext) -> str:
    template: Template = _env.get_template(template_name)
    return template.render(task=prompt_context.task, context=prompt_context.context, metadata=prompt_context.metadata or {})


def render_default_prompt(task: str, context: str = "", metadata: Dict[str, Any] | None = None) -> str:
    return render_prompt("default_prompt.j2", PromptContext(task=task, context=context, metadata=metadata))
