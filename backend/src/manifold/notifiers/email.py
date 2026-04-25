from __future__ import annotations

from email.message import EmailMessage
from typing import Any

import aiosmtplib

from manifold.config import settings
from manifold.notifiers import get_template_environment
from manifold.notifiers.base import (
    BaseNotifier,
    NotificationPayload,
    NotificationType,
    PreparedNotification,
)


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
        return {
            "smtp_host": config["smtp_host"],
            "smtp_port": int(config["smtp_port"]),
            "smtp_use_tls": bool(config.get("smtp_use_tls", True)),
            "from_address": config["from_address"],
            "to_address": config["to_address"],
            "subject": subject,
            "body": body,
            "notification_type": payload.type.value,
        }

    async def send(self, payload: NotificationPayload, config: dict[str, Any]) -> bool:
        prepared = self.prepare(payload, config)
        message = EmailMessage()
        message["From"] = str(config["from_address"])
        message["To"] = str(config["to_address"])
        message["Subject"] = prepared.subject
        message.set_content(prepared.body)
        await aiosmtplib.send(
            message,
            hostname=str(config["smtp_host"]),
            port=int(config["smtp_port"]),
            use_tls=bool(config.get("smtp_use_tls", True)),
            username=config.get("smtp_username") or settings.smtp_user or None,
            password=config.get("smtp_password") or settings.smtp_password or None,
        )
        return True

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
        errors: list[str] = []
        for key in ("smtp_host", "smtp_port", "from_address", "to_address"):
            if not config.get(key):
                errors.append(f"missing_{key}")
        return errors


__all__ = ["EmailNotifier"]
