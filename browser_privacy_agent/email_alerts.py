"""Email alert helper using SMTP."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from .config import CONFIG
from .logger import setup_logger

LOGGER = setup_logger("alerts")


def send_alert(subject: str, body: str) -> None:
    smtp = CONFIG.smtp
    if not (smtp.host and smtp.sender and smtp.recipient):
        LOGGER.warning("SMTP configuration incomplete; skipping alert: %s", subject)
        return
    message = EmailMessage()
    message["From"] = smtp.sender
    message["To"] = smtp.recipient
    message["Subject"] = subject
    message.set_content(body)
    LOGGER.info("Sending alert to %s", smtp.recipient)
    with smtplib.SMTP(smtp.host, smtp.port, timeout=20) as client:
        if smtp.use_tls:
            client.starttls()
        if smtp.username and smtp.password:
            client.login(smtp.username, smtp.password)
        client.send_message(message)
