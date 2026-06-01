from __future__ import annotations

import hashlib
import hmac
import re
from email.header import Header
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_master_dek
from manifold.config import settings
from manifold.email.factory import get_transport
from manifold.email.message import EmailMessage
from manifold.models.email_settings import InstanceEmailSettings
from manifold.models.email_suppression import EmailSuppression
from manifold.models.user import User
from manifold.notifiers import get_template_environment
from manifold.notifiers.base import (
    BaseNotifier,
    NotificationPayload,
    NotificationType,
    PreparedNotification,
)
from manifold.security.encryption import EncryptionService

logger = structlog.get_logger()


class EmailNotifier(BaseNotifier):
    notifier_type = "email"

    def _render_body(self, payload: NotificationPayload) -> str:
        template_name = {
            NotificationType.ALARM_FIRING: "email/alarm_firing.txt",
            NotificationType.ALARM_RESOLVED: "email/alarm_resolved.txt",
        }.get(payload.type)
        if template_name is None:
            return payload.body
        template = get_template_environment().get_template(template_name)
        return template.render(
            alarm_id=payload.alarm_id,
            alarm_name=payload.metadata.get("alarm_name") or payload.subject,
            alarm_explanation=payload.explanation
            or payload.metadata.get("alarm_explanation")
            or payload.body,
            fired_at=payload.metadata.get("fired_at"),
            resolved_at=payload.metadata.get("resolved_at"),
        )

    def prepare(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
    ) -> PreparedNotification:
        body = self._render_body(payload)
        subject = payload.subject
        return PreparedNotification(
            subject=subject,
            body=body,
            request_payload=self.build_request_payload(payload, config, subject, body),
        )

    def build_request_payload(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        # Only routing fields — no transport secrets, no injected context keys.
        return {
            "to_address": config["to_address"],
            "subject": subject,
            "body": body,
            "notification_type": payload.type.value,
        }

    async def send(self, payload: NotificationPayload, config: dict[str, Any]) -> bool:
        session: AsyncSession | None = config.get("_session")
        user_id: str | None = config.get("_user_id")
        if session is None:
            raise RuntimeError("EmailNotifier.send requires _session injected by dispatcher")

        to_address: str = config["to_address"]
        prepared = self.prepare(payload, config)

        # --- master-DEK block: load instance email settings + check suppression ---
        async def _load_settings_and_check_suppression() -> (
            tuple[bool, str, dict[str, Any], str | None, str | None]
        ):
            """Returns (suppressed, provider, transport_config, from_address, from_name)."""
            addr = to_address.strip().lower()
            master_key = EncryptionService().dek_master_key
            digest = hmac.new(master_key, addr.encode(), hashlib.sha256).digest()

            suppression_result = await session.execute(
                select(EmailSuppression).where(EmailSuppression.address_hmac == digest)
            )
            suppressed = suppression_result.scalar_one_or_none() is not None

            row = await session.get(InstanceEmailSettings, "default")
            if row is not None:
                _provider = row.provider
                _transport_config: dict[str, Any] = dict(row.config or {})
                _from_address = row.from_address or settings.smtp_from_address or None
                _from_name = row.from_name or None
            else:
                _provider = "smtp"
                _transport_config = {
                    "host": settings.smtp_host,
                    "port": settings.smtp_port,
                    "use_tls": settings.smtp_use_tls,
                    "username": settings.smtp_user,
                    "password": settings.smtp_password,
                }
                _from_address = settings.smtp_from_address or None
                _from_name = None

            return suppressed, _provider, _transport_config, _from_address, _from_name

        result: tuple[bool, str, dict[str, Any], str | None, str | None] = (
            await with_master_dek(_load_settings_and_check_suppression)
        )
        suppressed, provider, transport_config, global_from_address, global_from_name = result

        if suppressed:
            logger.info("email.suppressed", to_address=to_address)
            return False

        # Load user for From composition — username is a plaintext column, no user DEK needed.
        user: User | None = None
        if user_id is not None:
            user = await session.get(User, user_id)

        composed_from = _compose_from(
            global_from_address=global_from_address,
            global_from_name=global_from_name,
            user=user,
        )

        msg = EmailMessage(
            to=[to_address],
            subject=prepared.subject,
            html_body=prepared.body,
            text_body=prepared.body,
            from_address=composed_from,
            reply_to=None,
        )

        try:
            transport = get_transport(provider, transport_config)
            await transport.send(msg)
            return True
        except Exception:
            logger.exception("email.send_failed", to_address=to_address)
            return False

    async def test(self, config: dict[str, Any]) -> bool:
        return await self.send(
            NotificationPayload(
                type=NotificationType.TEST,
                subject="Manifold notifier test",
                body="This is a test notification from Manifold.",
            ),
            config,
        )

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        if not config.get("to_address"):
            return ["missing_to_address"]
        return []


def _compose_from(
    global_from_address: str | None,
    global_from_name: str | None,
    user: User | None,
) -> str | None:
    if not global_from_address:
        return None

    # Split local-part and domain
    at = global_from_address.rfind("@")
    if at < 0:
        return global_from_address
    local = global_from_address[:at]
    domain = global_from_address[at + 1 :]

    # Build plus-tag from username (plaintext column — no DEK needed)
    username = user.username if user is not None else None
    tag = re.sub(r"[^A-Za-z0-9._-]", "", username or "")
    if tag:
        # Truncate the entire local-part to RFC 5321 maximum of 64 chars
        composed_local = f"{local}+{tag}"[:64]
    else:
        composed_local = local

    composed_address = f"{composed_local}@{domain}"

    # Display name: first+last > username > email > "User"
    display_name: str
    if user is not None:
        first = user.first_name or ""
        last = user.last_name or ""
        full = f"{first} {last}".strip()
        if full:
            display_name = full
        elif user.username:
            display_name = user.username
        elif user.email:
            display_name = user.email
        else:
            display_name = "User"
    else:
        display_name = global_from_name or "User"

    encoded_name = Header(display_name, charset="utf-8").encode()
    return f"{encoded_name} <{composed_address}>"


__all__ = ["EmailNotifier"]
