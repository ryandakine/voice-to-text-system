"""Local LLM loader utilities."""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Dict, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .config import CONFIG
from .logger import setup_logger

LOGGER = setup_logger("llm")


class LocalLLM:
    """Wrapper around a locally hosted uncensored Qwen model."""

    def __init__(self) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is required for the local Qwen model.")
        model_name = CONFIG.model.model_name
        LOGGER.info("Loading local model %s with 4-bit quantization.", model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map=CONFIG.model.device_map,
            load_in_4bit=True,
            torch_dtype=torch.float16,
            trust_remote_code=True,
        )
        self.generation_config: Dict[str, Optional[float]] = {
            "temperature": CONFIG.model.temperature,
            "max_new_tokens": CONFIG.model.max_new_tokens,
        }
        self.lock = threading.Lock()

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text given a prompt using the configured parameters."""
        gen_kwargs = {**self.generation_config, **kwargs}
        if gen_kwargs.get("max_new_tokens", 0) > CONFIG.model.max_new_tokens:
            gen_kwargs["max_new_tokens"] = CONFIG.model.max_new_tokens
        LOGGER.info(
            "Running inference with temperature %.2f and max tokens %s",
            gen_kwargs.get("temperature"),
            gen_kwargs.get("max_new_tokens"),
        )
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=min(CONFIG.model.context_window, self.tokenizer.model_max_length),
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        with torch.inference_mode(), self.lock:
            output = self.model.generate(**inputs, **gen_kwargs)
        text = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return text[len(prompt) :].strip() if text.startswith(prompt) else text.strip()


@lru_cache(maxsize=1)
def get_local_llm() -> LocalLLM:
    """Return singleton instance of the local LLM."""
    return LocalLLM()
