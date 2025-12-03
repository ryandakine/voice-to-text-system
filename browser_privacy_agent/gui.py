"""Optional Gradio GUI for the AI browser."""

from __future__ import annotations

import asyncio
from typing import Dict

import gradio as gr

from .main import _run as run_task_async


def launch_gui() -> None:
    async def execute(task: str, url: str, context: str) -> str:
        await run_task_async(task, url or None, context)
        return "Task dispatched. Check logs for detailed output."

    def submit(task: str, url: str, context: str) -> str:
        return asyncio.run(execute(task, url, context))

    with gr.Blocks(title="AI Privacy Browser") as app:
        gr.Markdown("## Local AI Browser (MIT, optional GPLv3 redistribution)")
        task = gr.Textbox(label="Task", placeholder="Scrape and summarize uncensored content...")
        url = gr.Textbox(label="URL", placeholder="https://example.com")
        context = gr.Textbox(label="Context", lines=4)
        output = gr.Textbox(label="Status")
        run_button = gr.Button("Run")
        run_button.click(fn=submit, inputs=[task, url, context], outputs=output)
    app.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
