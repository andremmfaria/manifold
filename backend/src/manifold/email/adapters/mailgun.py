from __future__ import annotations

import hashlib
import hmac
import json

import httpx

from manifold.email.base import SuppressionEvent
from manifold.email.message import EmailMessage

_TIMEOUT = 15.0
_BASE_URL = {
    "us": "https://api.mailgun.net",
    "eu": "https://api.eu.mailgun.net",
}


class MailgunTransport:
    def __init__(self, config: dict) -> None:
        self._config = config

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if not config.get("api_key"):
            errors.append("missing_api_key")
        if not config.get("domain"):
            errors.append("missing_domain")
        if not config.get("region"):
            errors.append("missing_region")
        return errors

    async def send(self, msg: EmailMessage) -> str:
        api_key: str = self._config["api_key"]
        domain: str = self._config["domain"]
        region: str = self._config.get("region", "us")
        base_url = _BASE_URL.get(region, _BASE_URL["us"])
        url = f"{base_url}/v3/{domain}/messages"

        data: dict = {
            "from": msg.from_address,
            "to": msg.to,
            "subject": msg.subject,
            "html": msg.html_body,
        }
        if msg.text_body is not None:
            data["text"] = msg.text_body
        if msg.reply_to is not None:
            data["h:Reply-To"] = msg.reply_to

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, data=data, auth=("api", api_key))
            resp.raise_for_status()
            return resp.json()["id"]

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        # Mailgun signature lives inside the JSON body, not headers
        try:
            signing_key: str | None = self._config.get("webhook_signing_key")
            if not signing_key:
                return False

            payload = json.loads(body)
            sig_obj: dict = payload["signature"]
            timestamp: str = sig_obj["timestamp"]
            token: str = sig_obj["token"]
            signature: str = sig_obj["signature"]

            digest = hmac.new(
                signing_key.encode(),
                f"{timestamp}{token}".encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(digest, signature)
        except Exception:  # noqa: BLE001
            return False

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]:
        # Support both modern `event-data` envelope and flat shape
        event_data: dict = payload.get("event-data") or payload
        event: str = event_data.get("event", "")
        severity: str = event_data.get("severity", "")
        address: str = event_data.get("recipient", "")

        if not address:
            return []

        if event == "failed" and severity == "permanent":
            reason = "bounce"
        elif event == "complained":
            reason = "complaint"
        else:
            return []

        return [SuppressionEvent(address=address, reason=reason, provider="mailgun")]


__all__ = ["MailgunTransport"]
