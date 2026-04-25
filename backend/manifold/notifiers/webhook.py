from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from manifold.notifiers import get_template_environment
from manifold.notifiers.base import (
    BaseNotifier,
    NotificationPayload,
    NotificationType,
    PreparedNotification,
)


class WebhookNotifier(BaseNotifier):
    notifier_type = "webhook"

    def prepare(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
    ) -> PreparedNotification:
        subject = payload.subject
        body = payload.body
        request_payload = self.build_request_payload(payload, config, subject, body)
        if payload.type == NotificationType.ALARM_FIRING:
            template = get_template_environment().get_template("webhook/alarm_firing.json")
            rendered = template.render(
                alarm_id=payload.alarm_id,
                alarm_name=payload.metadata.get("alarm_name") or payload.subject,
                alarm_explanation=payload.explanation
                or payload.metadata.get("alarm_explanation")
                or payload.body,
                fired_at=payload.metadata.get("fired_at"),
                delivery_id=payload.metadata.get("delivery_id"),
            )
            body = rendered
            request_payload["body"] = body
            request_payload.update(json.loads(rendered))
        return PreparedNotification(
            subject=subject,
            body=body,
            request_payload=request_payload,
        )

    def build_request_payload(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        return {
            "event_type": payload.type.value,
            "subject": subject,
            "body": body,
            "metadata": dict(payload.metadata),
            "triggered_at": payload.metadata.get("triggered_at")
            or datetime.now(UTC).isoformat(),
            "alarm_id": payload.alarm_id,
        }

    async def send(self, payload: NotificationPayload, config: dict[str, Any]) -> bool:
        prepared = self.prepare(payload, config)
        method = str(config.get("method", "POST")).upper()
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                str(config["url"]),
                headers=dict(config.get("headers") or {}),
                json=prepared.request_payload,
            )
        return 200 <= response.status_code < 300

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
        return [] if config.get("url") else ["missing_url"]


__all__ = ["WebhookNotifier"]
