from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from manifold.email.base import SuppressionEvent
from manifold.email.message import EmailMessage


class SMTPTransport:
    def __init__(self, config: dict) -> None:
        self._config = config

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        for key in ("host", "port"):
            if not config.get(key):
                errors.append(f"missing_{key}")
        return errors

    async def send(self, msg: EmailMessage) -> str:
        cfg = self._config
        host: str = cfg["host"]
        port: int = int(cfg["port"])
        use_tls: bool = bool(cfg.get("use_tls", True))
        use_starttls: bool = bool(cfg.get("use_starttls", False))
        username: str | None = cfg.get("username") or None
        password: str | None = cfg.get("password") or None

        mime_msg = MIMEMultipart("alternative")
        mime_msg["From"] = msg.from_address or ""
        mime_msg["To"] = ", ".join(msg.to)
        mime_msg["Subject"] = msg.subject
        if msg.reply_to:
            mime_msg["Reply-To"] = msg.reply_to

        if msg.text_body:
            mime_msg.attach(MIMEText(msg.text_body, "plain"))
        mime_msg.attach(MIMEText(msg.html_body, "html"))

        await aiosmtplib.send(
            mime_msg,
            hostname=host,
            port=port,
            username=username,
            password=password,
            use_tls=use_tls,
            start_tls=use_starttls,
        )

        return mime_msg.get("Message-ID") or ""

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        return False

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]:
        return []


__all__ = ["SMTPTransport"]
