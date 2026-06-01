from __future__ import annotations

import hashlib
import hmac
from email.utils import parseaddr

import httpx

from manifold.email.base import SuppressionEvent
from manifold.email.message import EmailMessage

_BREVO_API = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 15.0


class BrevoTransport:
    def __init__(self, config: dict) -> None:
        self._config = config

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if not config.get("api_key"):
            errors.append("missing_api_key")
        return errors

    async def send(self, msg: EmailMessage) -> str:
        api_key: str = self._config["api_key"]

        # parseaddr handles both "Name <addr>" and bare "addr" forms
        display_name, email_addr = parseaddr(msg.from_address or "")
        sender: dict = {"email": email_addr or msg.from_address or ""}
        if display_name:
            sender["name"] = display_name

        payload: dict = {
            "sender": sender,
            "to": [{"email": a} for a in msg.to],
            "subject": msg.subject,
            "htmlContent": msg.html_body,
        }
        if msg.text_body is not None:
            payload["textContent"] = msg.text_body
        if msg.reply_to is not None:
            payload["replyTo"] = {"email": msg.reply_to}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _BREVO_API,
                json=payload,
                headers={
                    "api-key": api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
            )
            resp.raise_for_status()
            return str(resp.json().get("messageId", ""))

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        # NOTE: Brevo webhook signature scheme assumed (HMAC-SHA256 hex of raw body);
        # Brevo's official docs (as of 2026-06-01) do not publish a cryptographic
        # signing scheme — they recommend IP allowlisting instead. If Brevo adds
        # an official HMAC signature in the future, update the header name and scheme
        # to match. Current best-known candidate header: X-Brevo-Webhook-Signature.
        try:
            secret: str | None = self._config.get("webhook_secret")
            if not secret:
                return False

            norm = {k.lower(): v for k, v in headers.items()}
            provided = norm.get("x-brevo-webhook-signature", "")
            if not provided:
                return False

            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(provided, expected)
        except Exception:  # noqa: BLE001
            return False

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]:
        event: str = payload.get("event", "")
        address: str = payload.get("email", "")

        if event == "hard_bounce":
            return [SuppressionEvent(address=address, reason="bounce", provider="brevo")]
        if event == "spam":
            return [SuppressionEvent(address=address, reason="complaint", provider="brevo")]
        return []


__all__ = ["BrevoTransport"]
