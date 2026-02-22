"""Minimal SMTP email helper for admin notifications."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .config import SMTPConfig

logger = logging.getLogger(__name__)


class EmailSender:
    """Send plain-text emails via SMTP with optional TLS/auth."""

    def __init__(self, config: SMTPConfig):
        self.config = config

    @property
    def is_configured(self) -> bool:
        return bool(self.config.host)

    def send(self, *, to_address: str, subject: str, body: str) -> None:
        if not self.is_configured:
            raise RuntimeError("SMTP host not configured; cannot send email")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.from_address
        message["To"] = to_address
        message.set_content(body)

        try:
            with smtplib.SMTP(self.config.host, self.config.port, timeout=self.config.timeout_seconds) as server:
                server.ehlo()
                if self.config.use_tls:
                    server.starttls()
                    server.ehlo()
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)
                server.send_message(message)
        except Exception:  # pragma: no cover - network failures
            logger.exception("Failed to send email to %s", to_address)
            raise
