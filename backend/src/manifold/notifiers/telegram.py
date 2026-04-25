from __future__ import annotations

from typing import Any

import httpx

from manifold.notifiers import get_template_environment
from manifold.notifiers.base import (
    BaseNotifier,
    NotificationPayload,
    NotificationType,
    PreparedNotification,
)


class TelegramNotifier(BaseNotifier):
    notifier_type = "telegram"

    def _render_body(self, payload: NotificationPayload) -> str:
        if payload.type != NotificationType.ALARM_FIRING:
            return payload.body
        try:
            template = get_template_environment().get_template("telegram/alarm_firing.md")
            return template.render(
                alarm_id=payload.alarm_id,
                alarm_name=payload.metadata.get("alarm_name") or payload.subject,
                alarm_explanation=payload.explanation
                or payload.metadata.get("alarm_explanation")
                or payload.body,
                fired_at=payload.metadata.get("fired_at"),
            )
        except Exception:
            return payload.body

    def prepare(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
    ) -> PreparedNotification:
        body = self._render_body(payload)
        return PreparedNotification(
            subject=payload.subject,
            body=body,
            request_payload={"chat_id": config["chat_id"], "text": body, "parse_mode": "Markdown"},
        )

    async def send(self, payload: NotificationPayload, config: dict[str, Any]) -> bool:
        prepared = self.prepare(payload, config)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{config['bot_token']}/sendMessage",
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
        if not config.get("bot_token"):
            errors.append("missing_bot_token")
        if not config.get("chat_id"):
            errors.append("missing_chat_id")
        return errors


__all__ = ["TelegramNotifier"]
