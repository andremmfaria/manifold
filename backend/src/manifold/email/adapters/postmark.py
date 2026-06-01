from __future__ import annotations

import hmac

import httpx

from manifold.email.base import SuppressionEvent
from manifold.email.message import EmailMessage

_POSTMARK_API = "https://api.postmarkapp.com/email"
_TIMEOUT = 15.0


class PostmarkTransport:
    def __init__(self, config: dict) -> None:
        self._config = config

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if not config.get("api_key"):
            errors.append("missing_api_key")
        return errors

    async def send(self, msg: EmailMessage) -> str:
        api_key: str = self._config["api_key"]
        body: dict = {
            "From": msg.from_address,
            "To": ", ".join(msg.to),
            "Subject": msg.subject,
            "HtmlBody": msg.html_body,
            "MessageStream": "outbound",
        }
        if msg.text_body is not None:
            body["TextBody"] = msg.text_body
        if msg.reply_to is not None:
            body["ReplyTo"] = msg.reply_to

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _POSTMARK_API,
                json=body,
                headers={
                    "X-Postmark-Server-Token": api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()["MessageID"]

    def verify_webhook(self, headers: dict, body: bytes) -> bool:  # noqa: ARG002
        try:
            webhook_token: str | None = self._config.get("webhook_token")
            if not webhook_token:
                return False
            # Normalize header keys to lower-case for case-insensitive lookup
            normalized = {k.lower(): v for k, v in headers.items()}
            provided = normalized.get("x-postmark-signature", "")
            return hmac.compare_digest(provided, webhook_token)
        except Exception:  # noqa: BLE001
            return False

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]:
        record_type = payload.get("RecordType")
        address = payload.get("Email", "")
        if record_type == "Bounce":
            return [SuppressionEvent(address=address, reason="bounce", provider="postmark")]
        if record_type == "SpamComplaint":
            return [SuppressionEvent(address=address, reason="complaint", provider="postmark")]
        return []


__all__ = ["PostmarkTransport"]
