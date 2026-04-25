from __future__ import annotations

import json
from typing import Any

import httpx

from manifold.notifiers import get_template_environment
from manifold.notifiers.base import (
    BaseNotifier,
    NotificationPayload,
    NotificationType,
    PreparedNotification,
)


class SlackNotifier(BaseNotifier):
    notifier_type = "slack"

    def _render_body(self, payload: NotificationPayload) -> str:
        if payload.type != NotificationType.ALARM_FIRING:
            return payload.body
        try:
            template = get_template_environment().get_template("slack/alarm_firing.json")
            rendered = template.render(
                alarm_id=payload.alarm_id,
                alarm_name=payload.metadata.get("alarm_name") or payload.subject,
                alarm_explanation=payload.explanation
                or payload.metadata.get("alarm_explanation")
                or payload.body,
                fired_at=payload.metadata.get("fired_at"),
                delivery_id=payload.metadata.get("delivery_id"),
            )
            return rendered
        except Exception:
            return payload.body

    def prepare(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
    ) -> PreparedNotification:
        body = self._render_body(payload)
        request_payload: dict[str, Any]
        try:
            request_payload = json.loads(body)
        except Exception:
            request_payload = {"text": payload.body}
        if config.get("channel"):
            request_payload["channel"] = config["channel"]
        return PreparedNotification(
            subject=payload.subject,
            body=body,
            request_payload=request_payload,
        )

    async def send(self, payload: NotificationPayload, config: dict[str, Any]) -> bool:
        prepared = self.prepare(payload, config)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    str(config["webhook_url"]),
                    json=prepared.request_payload,
                )
            return 200 <= response.status_code < 300
        except httpx.HTTPError:
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
        errors: list[str] = []
        if not config.get("webhook_url"):
            errors.append("missing_webhook_url")
        return errors


__all__ = ["SlackNotifier"]
