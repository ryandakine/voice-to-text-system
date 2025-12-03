"""Entry point for the privacy-focused AI browser."""

from __future__ import annotations

import argparse
import asyncio
from typing import List

from .config import CONFIG
from .logger import log_json, setup_logger
from .llm_loader import get_local_llm
from .prompting import render_default_prompt
from .validator_rotator import ValidatorRotator
from .playwright_wrapper import run_task
from .email_alerts import send_alert

LOGGER = setup_logger("main")


async def _run(task: str, url: str | None, context: str) -> None:
    prompt = render_default_prompt(task=task, context=context)
    LOGGER.info("Rendered prompt with length %s", len(prompt))
    model = get_local_llm()
    response = model.generate(prompt)
    log_json(LOGGER, "primary_response", {"response": response})

    validator = ValidatorRotator()
    results = validator.validate(prompt, response)
    for result in results:
        LOGGER.info("Validator %s: ok=%s confidence=%.2f", result.validator, result.ok, result.confidence)

    if url:
        try:
            html = await run_task(url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Playwright task failed: %s", exc)
            send_alert("Playwright failure", f"Task: {task}\nError: {exc}")
            return
        summary_prompt = render_default_prompt(
            task=f"Summarize the following HTML for the task: {task}",
            context=html[-50_000:],
        )
        summary = model.generate(summary_prompt)
        log_json(LOGGER, "summary", {"summary": summary})


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Linux-native AI browser demo")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--url", help="Optional URL to target")
    parser.add_argument("--context", default="", help="Additional context for the prompt")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        asyncio.run(_run(args.task, args.url, args.context))
    except RuntimeError as exc:
        LOGGER.error("Fatal error: %s", exc)
        send_alert("AI Browser fatal error", str(exc))


if __name__ == "__main__":
    main()
