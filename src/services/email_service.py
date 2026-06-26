"""SMTP email sender for appointment confirmation/reminder emails.

Provider-agnostic: any SMTP host works (Gmail app password, Resend, SendGrid,
SES…). smtplib is blocking, so sends run in a worker thread to avoid stalling
the voice pipeline's event loop.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import structlog

log = structlog.get_logger(__name__)


class EmailService:
    def __init__(
        self,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        from_addr: str | None,
        from_name: str = "Clínica Dental Smile",
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_addr = (from_addr or "").strip() or None
        self._from_name = from_name
        self._use_tls = use_tls

    @property
    def configured(self) -> bool:
        """True only if we have enough to actually send."""
        return bool(self._host and self._from_addr)

    async def send(self, to: str, subject: str, body: str) -> None:
        """Send a plain-text email. Raises on failure (caller maps to an envelope)."""
        await asyncio.to_thread(self._send_sync, to, subject, body)
        log.info("email.sent", to=to, subject=subject)

    def _send_sync(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = f"{self._from_name} <{self._from_addr}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=20) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(msg)
