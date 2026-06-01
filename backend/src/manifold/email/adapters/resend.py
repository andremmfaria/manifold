from __future__ import annotations

import base64
import hashlib
import hmac

import httpx

from manifold.email.base import SuppressionEvent
from manifold.email.message import EmailMessage

_RESEND_API = "https://api.resend.com/emails"
_TIMEOUT = 15.0


class ResendTransport:
    def __init__(self, config: dict) -> None:
        self._config = config

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if not config.get("api_key"):
            errors.append("missing_api_key")
        return errors

    async def send(self, msg: EmailMessage) -> str:
        api_key: str = self._config["api_key"]
        payload: dict = {
            "from": msg.from_address,
            "to": msg.to,
            "subject": msg.subject,
            "html": msg.html_body,
        }
        if msg.text_body is not None:
            payload["text"] = msg.text_body
        if msg.reply_to is not None:
            payload["reply_to"] = msg.reply_to
        if msg.tags:
            payload["tags"] = [{"name": "tag", "value": t} for t in msg.tags]

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _RESEND_API,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            return resp.json()["id"]

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        try:
            secret: str | None = self._config.get("webhook_secret")
            if not secret:
                return False

            # Normalize header keys to lowercase for case-insensitive lookup
            norm = {k.lower(): v for k, v in headers.items()}
            svix_id = norm.get("svix-id", "")
            svix_timestamp = norm.get("svix-timestamp", "")
            svix_signature = norm.get("svix-signature", "")
            if not (svix_id and svix_timestamp and svix_signature):
                return False

            # Svix secret: strip optional "whsec_" prefix then base64-decode
            raw_secret = secret
            if raw_secret.startswith("whsec_"):
                raw_secret = raw_secret[len("whsec_"):]
            key_bytes = base64.b64decode(raw_secret)

            # Signed payload: "{svix_id}.{svix_timestamp}.{body}"
            signed_payload = f"{svix_id}.{svix_timestamp}.{body.decode()}".encode()
            digest = hmac.new(key_bytes, signed_payload, hashlib.sha256).digest()
            our_sig = base64.b64encode(digest).decode()

            # svix-signature is space-separated tokens of the form "v1,<b64sig>"
            for token in svix_signature.split():
                parts = token.split(",", 1)
                if len(parts) == 2 and hmac.compare_digest(parts[1], our_sig):
                    return True
            return False
        except Exception:  # noqa: BLE001
            return False

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]:
        event_type: str = payload.get("type", "")
        if event_type not in ("email.bounced", "email.complained"):
            return []

        reason = "bounce" if event_type == "email.bounced" else "complaint"
        raw_to = payload.get("data", {}).get("to", [])
        addresses: list[str] = [raw_to] if isinstance(raw_to, str) else list(raw_to)

        return [
            SuppressionEvent(address=addr, reason=reason, provider="resend")
            for addr in addresses
        ]


__all__ = ["ResendTransport"]
