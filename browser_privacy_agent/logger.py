"""Logging helpers for the AI browser."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

from .config import CONFIG


def setup_logger(name: str) -> logging.Logger:
    """Create a configured logger writing to the configured log directory."""
    log_dir = CONFIG.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(log_dir / f"{name}.log", maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


def log_json(logger: logging.Logger, event: str, payload: Dict[str, Any]) -> None:
    """Helper to log structured events."""
    logger.info("%s | %s", event, json.dumps(payload, ensure_ascii=False, sort_keys=True))
