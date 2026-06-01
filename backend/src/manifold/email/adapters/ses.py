from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from botocore.config import Config
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509 import load_pem_x509_certificate

from manifold.email.base import SuppressionEvent
from manifold.email.message import EmailMessage

logger = logging.getLogger(__name__)

# Module-level cert cache: url -> (pem_bytes, fetched_at)
_cert_cache: dict[str, tuple[bytes, datetime]] = {}
_cert_cache_lock = asyncio.Lock()
_CERT_TTL = timedelta(hours=24)

# SNS canonical string fields, in documented byte-order per AWS docs
# https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html
_NOTIFICATION_FIELDS = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]
_SUBSCRIPTION_FIELDS = [
    "Message",
    "MessageId",
    "SubscribeURL",
    "Timestamp",
    "Token",
    "TopicArn",
    "Type",
]

_BOTOCORE_CFG = Config(
    connect_timeout=2,
    read_timeout=2,
    retries={"max_attempts": 0},
)


class SESTransport:
    def __init__(self, config: dict, client: Any = None) -> None:
        self._config = config
        self._client = client

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------

    def validate_config(self, config: dict) -> list[str]:
        errors: list[str] = []
        if not config.get("region"):
            errors.append("missing_region")
        return errors

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def send(self, msg: EmailMessage) -> str:
        cfg = self._config
        region: str = cfg["region"]
        access_key: str | None = cfg.get("access_key_id") or None
        secret_key: str | None = cfg.get("secret_access_key") or None

        body: dict[str, Any] = {
            "Subject": {"Data": msg.subject},
            "Body": {"Html": {"Data": msg.html_body}},
        }
        if msg.text_body:
            body["Body"]["Text"] = {"Data": msg.text_body}

        kwargs: dict[str, Any] = {
            "Source": msg.from_address or "",
            "Destination": {"ToAddresses": msg.to},
            "Message": body,
        }
        if msg.reply_to:
            kwargs["ReplyToAddresses"] = [msg.reply_to]

        if self._client is not None:
            # Injected client — caller owns lifecycle
            try:
                resp = await self._client.send_email(**kwargs)
            except Exception as exc:
                raise _wrap_cred_error(exc) from exc
            return resp["MessageId"]

        # No injected client — create a scoped one per send
        import aiobotocore.session  # noqa: PLC0415  (deferred import; aiobotocore inits loop on import)

        session = aiobotocore.session.get_session()
        try:
            async with session.create_client(
                "ses",
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=_BOTOCORE_CFG,
            ) as client:
                resp = await client.send_email(**kwargs)
        except Exception as exc:
            raise _wrap_cred_error(exc) from exc
        return resp["MessageId"]

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return False

        msg_type = payload.get("Type", "")

        if msg_type == "SubscriptionConfirmation":
            valid = _run_sync(_verify_sns_signature(payload))
            if valid:
                subscribe_url = payload.get("SubscribeURL", "")
                if subscribe_url:
                    _run_sync(_confirm_subscription(subscribe_url))
            return valid

        if msg_type == "Notification":
            return _run_sync(_verify_sns_signature(payload))

        return False

    # ------------------------------------------------------------------
    # Webhook parsing
    # ------------------------------------------------------------------

    def parse_webhook(self, payload: dict) -> list[SuppressionEvent]:
        raw_message = payload.get("Message")
        if not raw_message:
            return []

        try:
            inner = json.loads(raw_message)
        except (json.JSONDecodeError, ValueError):
            return []

        notification_type = inner.get("notificationType") or inner.get("eventType", "")
        events: list[SuppressionEvent] = []

        if notification_type == "Bounce":
            for recipient in inner.get("bounce", {}).get("bouncedRecipients", []):
                address = recipient.get("emailAddress", "")
                if address:
                    events.append(
                        SuppressionEvent(address=address, reason="bounce", provider="ses")
                    )

        elif notification_type == "Complaint":
            for recipient in inner.get("complaint", {}).get("complainedRecipients", []):
                address = recipient.get("emailAddress", "")
                if address:
                    events.append(
                        SuppressionEvent(address=address, reason="complaint", provider="ses")
                    )

        return events


# ------------------------------------------------------------------
# Helpers (module-private)
# ------------------------------------------------------------------


def _wrap_cred_error(exc: Exception) -> Exception:
    """Re-wrap NoCredentials / metadata-timeout as a clear RuntimeError; else pass through."""
    exc_name = type(exc).__name__
    if exc_name in ("NoCredentialsError", "NoRegionError", "EndpointResolutionError"):
        return RuntimeError(f"SES: no credentials and IAM metadata unavailable: {exc}")
    # ConnectTimeoutError is the botocore class for metadata probe timeout
    if "ConnectTimeout" in exc_name or "ReadTimeout" in exc_name:
        return RuntimeError(f"SES: no credentials and IAM metadata unavailable: {exc}")
    return exc


def _build_canonical_string(payload: dict, fields: list[str]) -> bytes:
    """Build SNS canonical string for signature verification.

    Per AWS docs: for each field present (in the given order), append
    "<field_name>\n<value>\n".  Fields absent from the payload are skipped.
    """
    parts: list[str] = []
    for field in fields:
        value = payload.get(field)
        if value is not None:
            parts.append(field)
            parts.append(str(value))
    # Each key and value is followed by a newline
    return "\n".join(parts).encode() + b"\n" if parts else b""


async def _fetch_cert(url: str) -> bytes:
    """Fetch PEM cert bytes with a 24h module-level cache. Validates host."""
    from urllib.parse import urlparse  # noqa: PLC0415

    parsed = urlparse(url)
    if not (parsed.hostname or "").endswith(".amazonaws.com"):
        raise ValueError(f"SNS cert URL host not trusted: {parsed.hostname!r}")

    async with _cert_cache_lock:
        cached = _cert_cache.get(url)
        if cached is not None:
            pem_bytes, fetched_at = cached
            if datetime.now(tz=UTC) - fetched_at < _CERT_TTL:
                return pem_bytes

        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            pem_bytes = resp.content

        _cert_cache[url] = (pem_bytes, datetime.now(tz=UTC))
        return pem_bytes


async def _verify_sns_signature(payload: dict) -> bool:
    """Verify SNS message signature; returns False on any error (never raises)."""
    try:
        sig_version = payload.get("SignatureVersion", "1")
        cert_url = payload.get("SigningCertURL", "")
        signature_b64 = payload.get("Signature", "")

        pem = await _fetch_cert(cert_url)
        cert = load_pem_x509_certificate(pem)
        public_key = cert.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            # SNS signing certificates are always RSA.
            logger.debug("SNS signing cert is not RSA; rejecting")
            return False

        msg_type = payload.get("Type", "")
        if msg_type == "Notification":
            fields = _NOTIFICATION_FIELDS
        else:
            fields = _SUBSCRIPTION_FIELDS

        canonical = _build_canonical_string(payload, fields)
        signature = base64.b64decode(signature_b64)

        hash_algo: hashes.HashAlgorithm
        if sig_version == "2":
            hash_algo = hashes.SHA256()
        else:
            hash_algo = hashes.SHA1()  # noqa: S303  (SNS v1 mandates SHA1)

        public_key.verify(signature, canonical, padding.PKCS1v15(), hash_algo)
        return True

    except Exception:
        logger.debug("SNS signature verification failed", exc_info=True)
        return False


async def _confirm_subscription(url: str) -> None:
    """Fire-and-forget GET to the SNS SubscribeURL; swallows all errors."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            await http.get(url)
    except Exception:
        logger.warning("Failed to confirm SNS subscription at %s", url, exc_info=True)


def _run_sync(coro: Any) -> Any:
    """Run a coroutine in the current event loop if one exists, else create one.

    verify_webhook is a sync method on the Protocol; we bridge to async here.
    Using asyncio.get_event_loop().run_until_complete would block a running loop,
    so we detect and use asyncio.run_coroutine_threadsafe when inside an existing loop
    (FastAPI / anyio context), or asyncio.run when called from plain sync code.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — plain sync context (tests, scripts)
        return asyncio.run(coro)

    # Running inside an event loop (FastAPI handler calling verify_webhook sync).
    # We can't asyncio.run() here.  Run in a thread executor instead so we don't
    # block the loop.
    import concurrent.futures  # noqa: PLC0415

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


__all__ = ["SESTransport"]
