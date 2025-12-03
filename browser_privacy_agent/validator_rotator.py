"""Cross-model validation rotator for hallucination detection."""

from __future__ import annotations

import json
import torch
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .config import CONFIG, ValidatorConfig
from .email_alerts import send_alert
from .logger import log_json, setup_logger

LOGGER = setup_logger("validator")


@dataclass
class ValidationResult:
    validator: str
    ok: bool
    confidence: float
    notes: str
    sanitized_prompt: Optional[str] = None


class ValidatorRotator:
    """Runs validations across configured validators to detect hallucinations."""

    def __init__(self, validators: Optional[List[ValidatorConfig]] = None) -> None:
        self.validators = validators or CONFIG.validators
        self.executor = ThreadPoolExecutor(max_workers=max(1, len(self.validators)))

    def close(self) -> None:
        self.executor.shutdown(wait=False)

    def _sanitize(self, text: str) -> str:
        # rudimentary profanity sanitation to appease stricter models
        replacements = {
            "fuck": "fudge",
            "shit": "shoot",
            "bitch": "person",
        }
        sanitized = text
        for bad, good in replacements.items():
            sanitized = sanitized.replace(bad, good)
        return sanitized

    def _run_validator(self, validator: ValidatorConfig, prompt: str, primary: str) -> ValidationResult:
        LOGGER.info("Validator %s running", validator.name)
        sanitized_prompt = self._sanitize(prompt) if validator.sanitize_inputs else prompt
        try:
            if validator.kind == "local-deepseek":
                from transformers import AutoModelForCausalLM, AutoTokenizer

                tokenizer = AutoTokenizer.from_pretrained(validator.model_name, trust_remote_code=True)
                model = AutoModelForCausalLM.from_pretrained(
                    validator.model_name,
                    device_map="auto",
                    load_in_4bit=True,
                    trust_remote_code=True,
                )
                inputs = tokenizer(sanitized_prompt + "\n" + primary, return_tensors="pt", truncation=True)
                inputs = {k: v.to(model.device) for k, v in inputs.items()}
                with torch.inference_mode():  # type: ignore[name-defined]
                    output = model.generate(**inputs, max_new_tokens=256, temperature=0.2)
                text = tokenizer.decode(output[0], skip_special_tokens=True)
                ok = "hallucination" not in text.lower()
                confidence = 0.6 if ok else 0.1
                notes = text[-512:]
            else:
                # Generic stub for API-based validators (Claude, OpenAI, etc.)
                if validator.api_key:
                    LOGGER.info("Would call external API %s (disabled in privacy mode).", validator.kind)
                ok = True
                confidence = 0.5
                notes = "API validator stub executed"
        except Exception as exc:  # noqa: BLE001
            ok = False
            confidence = 0.0
            notes = f"Validator {validator.name} failed: {exc}"
            send_alert(
                subject=f"Validator failure: {validator.name}",
                body=f"Primary output: {primary}\nError: {exc}",
            )
        log_json(
            LOGGER,
            "validator_result",
            {
                "validator": validator.name,
                "ok": ok,
                "confidence": confidence,
                "notes": notes,
                "sanitized_prompt": sanitized_prompt,
            },
        )
        return ValidationResult(validator=validator.name, ok=ok, confidence=confidence, notes=notes, sanitized_prompt=sanitized_prompt)

    def validate(self, prompt: str, primary_response: str) -> List[ValidationResult]:
        futures: List[Future[ValidationResult]] = []
        for validator in self.validators:
            if not validator.enabled:
                continue
            futures.append(self.executor.submit(self._run_validator, validator, prompt, primary_response))
        results = [future.result() for future in futures]
        issues = [res for res in results if not res.ok]
        if issues:
            send_alert(
                subject="Hallucination detected",
                body=json.dumps(
                    {
                        "prompt": prompt,
                        "primary": primary_response,
                        "issues": [res.__dict__ for res in issues],
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    indent=2,
                ),
            )
        return results
