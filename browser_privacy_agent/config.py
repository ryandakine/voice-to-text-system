"""Configuration loading utilities for the privacy-focused browser agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv


ENV_PATH = Path(os.getenv("AI_BROWSER_ENV_FILE", ".env"))
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


@dataclass
class SMTPConfig:
    host: Optional[str] = None
    port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    use_tls: bool = True


@dataclass
class ValidatorConfig:
    name: str
    kind: str
    model_name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    enabled: bool = True
    sanitize_inputs: bool = True


@dataclass
class BrowserConfig:
    headless: bool = True
    stealth: bool = True
    navigation_timeout: int = 45000
    max_retries: int = 3
    user_agents: List[str] = field(default_factory=list)
    request_intercept_patterns: List[str] = field(default_factory=list)


@dataclass
class ModelConfig:
    model_name: str = "DavidAU/Qwen3-8B-64k-Context-2X-Josiefied-Uncensored"
    max_new_tokens: int = int(os.getenv("AI_BROWSER_MAX_NEW_TOKENS", "2048"))
    temperature: float = float(os.getenv("AI_BROWSER_TEMPERATURE", "1.2"))
    context_window: int = int(os.getenv("AI_BROWSER_CONTEXT_WINDOW", "16384"))
    device_map: str = os.getenv("AI_BROWSER_DEVICE_MAP", "auto")


@dataclass
class AppConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    validators: List[ValidatorConfig] = field(default_factory=list)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    enable_gui: bool = bool(int(os.getenv("AI_BROWSER_ENABLE_GUI", "0")))
    nginx_proxy: bool = bool(int(os.getenv("AI_BROWSER_ENABLE_NGINX", "0")))
    log_dir: Path = Path(os.getenv("AI_BROWSER_LOG_DIR", "logs"))


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Brave Chrome/120.0 Safari/537.36",
]


def build_config() -> AppConfig:
    """Create application configuration by reading environment variables."""

    validators: List[ValidatorConfig] = []
    idx = 1
    while True:
        prefix = f"AI_BROWSER_VALIDATOR_{idx}_"
        if f"{prefix}NAME" not in os.environ:
            break
        validators.append(
            ValidatorConfig(
                name=os.getenv(f"{prefix}NAME", f"validator-{idx}"),
                kind=os.getenv(f"{prefix}KIND", "openai"),
                model_name=os.getenv(f"{prefix}MODEL"),
                api_base=os.getenv(f"{prefix}API_BASE"),
                api_key=os.getenv(f"{prefix}API_KEY"),
                enabled=bool(int(os.getenv(f"{prefix}ENABLED", "1"))),
                sanitize_inputs=bool(int(os.getenv(f"{prefix}SANITIZE", "1"))),
            )
        )
        idx += 1

    browser_config = BrowserConfig(
        headless=bool(int(os.getenv("AI_BROWSER_HEADLESS", "1"))),
        stealth=bool(int(os.getenv("AI_BROWSER_STEALTH", "1"))),
        navigation_timeout=int(os.getenv("AI_BROWSER_NAVIGATION_TIMEOUT", "45000")),
        max_retries=int(os.getenv("AI_BROWSER_MAX_RETRIES", "3")),
        user_agents=[ua.strip() for ua in os.getenv("AI_BROWSER_USER_AGENTS", "").split("|") if ua.strip()] or DEFAULT_USER_AGENTS,
        request_intercept_patterns=[
            pattern.strip()
            for pattern in os.getenv("AI_BROWSER_BLOCK_PATTERNS", "telemetry|tracking|analytics").split("|")
            if pattern.strip()
        ],
    )

    smtp_config = SMTPConfig(
        host=os.getenv("AI_BROWSER_SMTP_HOST"),
        port=int(os.getenv("AI_BROWSER_SMTP_PORT", "587")),
        username=os.getenv("AI_BROWSER_SMTP_USERNAME"),
        password=os.getenv("AI_BROWSER_SMTP_PASSWORD"),
        sender=os.getenv("AI_BROWSER_SMTP_SENDER"),
        recipient=os.getenv("AI_BROWSER_SMTP_RECIPIENT"),
        use_tls=bool(int(os.getenv("AI_BROWSER_SMTP_TLS", "1"))),
    )

    config = AppConfig(
        model=ModelConfig(),
        validators=validators,
        browser=browser_config,
        smtp=smtp_config,
        enable_gui=bool(int(os.getenv("AI_BROWSER_ENABLE_GUI", "0"))),
        nginx_proxy=bool(int(os.getenv("AI_BROWSER_ENABLE_NGINX", "0"))),
        log_dir=Path(os.getenv("AI_BROWSER_LOG_DIR", "logs")),
    )

    config.log_dir.mkdir(parents=True, exist_ok=True)
    return config


CONFIG = build_config()
