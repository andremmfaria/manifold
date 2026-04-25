from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, with_user_dek
from manifold.config import settings
from manifold.models.alarm import (
    AlarmDefinition,
    AlarmFiringEvent,
    AlarmNotifierAssignment,
)
from manifold.models.notification_delivery import NotificationDelivery
from manifold.models.notifier import NotifierConfig
from manifold.notifiers.base import BaseNotifier, NotificationPayload, NotificationType
from manifold.notifiers.registry import registry

logger = structlog.get_logger()


class NotifierDispatcher:
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 30

    def __init__(self, session: AsyncSession):
        self._session = session

    async def dispatch_for_firing_event(self, alarm_firing_event_id: str) -> None:
        event_result = await self._session.execute(
            select(AlarmFiringEvent.__table__.c.alarm_id).where(
                AlarmFiringEvent.__table__.c.id == parse_uuid(alarm_firing_event_id)
            )
        )
        alarm_id = event_result.scalar_one_or_none()
        if alarm_id is None:
            return
        owner_result = await self._session.execute(
            select(AlarmDefinition.__table__.c.user_id).where(
                AlarmDefinition.__table__.c.id == alarm_id
            )
        )
        owner_user_id = owner_result.scalar_one_or_none()
        if owner_user_id is None:
            return

        async def _dispatch() -> int:
            event = await self._session.get(AlarmFiringEvent, parse_uuid(alarm_firing_event_id))
            alarm = await self._session.get(AlarmDefinition, str(alarm_id))
            if event is None or alarm is None:
                return 0
            assignment_result = await self._session.execute(
                select(AlarmNotifierAssignment.notifier_id)
                .where(AlarmNotifierAssignment.alarm_id == str(alarm.id))
                .order_by(AlarmNotifierAssignment.created_at.asc())
            )
            notifier_ids = [str(item) for item in assignment_result.scalars().all()]
            if settings.system_notifier_id:
                notifier_ids.append(settings.system_notifier_id)
            else:
                logger.warning(
                    "notifiers.system_notifier_missing",
                    alarm_firing_event_id=alarm_firing_event_id,
                )
            payload = self._build_alarm_payload(alarm, event)
            delivered = 0
            for notifier_id in list(dict.fromkeys(notifier_ids)):
                sent = await self._dispatch_to_notifier_id(
                    notifier_id=notifier_id,
                    payload=payload,
                    alarm_firing_event_id=alarm_firing_event_id,
                )
                if sent:
                    delivered += 1
            event.notifications_sent = delivered
            await self._session.commit()
            return delivered

        await with_user_dek(self._session, str(owner_user_id), _dispatch)

    async def dispatch_system_notification(
        self,
        notification_type: str,
        notifier_ids: list[str],
        notifier_owner_user_id: str,
        affected_user_id: str,
        payload: NotificationPayload,
    ) -> None:
        target_ids = list(dict.fromkeys(str(item) for item in notifier_ids))
        if notification_type == NotificationType.SYSTEM_EVENT.value and settings.system_notifier_id:
            target_ids.append(settings.system_notifier_id)
        elif (
            notification_type == NotificationType.SYSTEM_EVENT.value
            and not settings.system_notifier_id
        ):
            logger.warning(
                "notifiers.system_notifier_missing",
                affected_user_id=affected_user_id,
            )
        if not target_ids:
            return

        for notifier_id in list(dict.fromkeys(target_ids)):
            await self._dispatch_to_notifier_id(
                notifier_id=notifier_id,
                payload=payload,
                delivery_user_id=notifier_owner_user_id,
            )

    async def dispatch_test(self, notifier_id: str, owner_user_id: str) -> dict[str, bool]:
        async def _dispatch() -> dict[str, bool]:
            notifier_config = await self._session.get(NotifierConfig, parse_uuid(notifier_id))
            if notifier_config is None or not notifier_config.is_enabled:
                return {"delivered": False}
            try:
                notifier = registry.get(notifier_config.type)
            except KeyError:
                return {"delivered": False}
            delivered = await self._dispatch_with_retry(
                notifier,
                NotificationPayload(
                    type=NotificationType.TEST,
                    subject="Manifold notifier test",
                    body="This is a test notification from Manifold.",
                    metadata={"triggered_at": datetime.now(UTC).isoformat()},
                ),
                dict(notifier_config.config or {}),
                notifier_id=str(notifier_config.id),
                delivery_user_id=str(notifier_config.user_id),
                max_attempts=1,
            )
            return {"delivered": delivered}

        return await with_user_dek(self._session, owner_user_id, _dispatch)

    async def _dispatch_to_notifier_id(
        self,
        notifier_id: str,
        payload: NotificationPayload,
        alarm_firing_event_id: str | None = None,
        delivery_user_id: str | None = None,
    ) -> bool:
        owner_result = await self._session.execute(
            select(NotifierConfig.__table__.c.user_id).where(
                NotifierConfig.__table__.c.id == parse_uuid(notifier_id)
            )
        )
        notifier_owner_user_id = owner_result.scalar_one_or_none()
        if notifier_owner_user_id is None:
            logger.warning("notifiers.notifier_missing", notifier_id=notifier_id)
            return False

        async def _dispatch() -> bool:
            notifier_config = await self._session.get(NotifierConfig, parse_uuid(notifier_id))
            if notifier_config is None or not notifier_config.is_enabled:
                return False
            try:
                notifier = registry.get(notifier_config.type)
            except KeyError:
                logger.warning(
                    "notifiers.type_unregistered",
                    notifier_id=notifier_id,
                    notifier_type=notifier_config.type,
                )
                return False
            return await self._dispatch_with_retry(
                notifier,
                payload,
                dict(notifier_config.config or {}),
                notifier_id=str(notifier_config.id),
                delivery_user_id=delivery_user_id or str(notifier_config.user_id),
                alarm_firing_event_id=alarm_firing_event_id,
            )

        return await with_user_dek(self._session, str(notifier_owner_user_id), _dispatch)

    async def _dispatch_with_retry(
        self,
        notifier: BaseNotifier,
        payload: NotificationPayload,
        config: dict[str, Any],
        delivery_user_id: str | None = None,
        alarm_firing_event_id: str | None = None,
        notifier_id: str | None = None,
        max_attempts: int | None = None,
    ) -> bool:
        errors = notifier.validate_config(config)
        now = datetime.now(UTC)
        delivery = NotificationDelivery(
            alarm_firing_event_id=(
                parse_uuid(alarm_firing_event_id) if alarm_firing_event_id else None
            ),
            notifier_id=parse_uuid(notifier_id) if notifier_id else None,
            user_id=parse_uuid(delivery_user_id) if delivery_user_id else None,
            notification_type=payload.type.value,
            status="pending",
            attempt_count=0,
            first_attempted_at=now,
        )
        self._session.add(delivery)
        await self._session.flush()
        delivery_payload = replace(
            payload,
            metadata={
                **dict(payload.metadata),
                "delivery_id": str(delivery.id),
                "triggered_at": payload.metadata.get("triggered_at") or now.isoformat(),
            },
        )
        prepared = notifier.prepare(delivery_payload, config)
        delivery.rendered_subject = prepared.subject
        delivery.rendered_body = prepared.body
        delivery.request_payload = prepared.request_payload
        if errors:
            delivery.status = "failed"
            delivery.last_attempted_at = now
            delivery.error_message = ",".join(errors)
            delivery.response_detail = {"validation_errors": errors}
            await self._session.commit()
            return False

        attempts = max_attempts or self.MAX_ATTEMPTS
        for attempt in range(1, attempts + 1):
            attempt_time = datetime.now(UTC)
            delivery.attempt_count = attempt
            delivery.last_attempted_at = attempt_time
            if attempt == 1:
                delivery.first_attempted_at = attempt_time
            try:
                delivered = await notifier.send(delivery_payload, config)
                if delivered:
                    delivery.status = "delivered"
                    delivery.delivered_at = datetime.now(UTC)
                    delivery.response_detail = {"delivered": True, "attempt": attempt}
                    await self._session.commit()
                    return True
                delivery.status = "failed"
                delivery.error_message = "delivery_failed"
                delivery.response_detail = {"delivered": False, "attempt": attempt}
            except httpx.HTTPError as exc:
                response = exc.response
                delivery.status = "failed"
                delivery.error_message = str(exc)
                delivery.response_detail = {
                    "attempt": attempt,
                    "error_type": exc.__class__.__name__,
                    "status_code": response.status_code if response is not None else None,
                    "body": response.text if response is not None else None,
                }
            except Exception as exc:  # noqa: BLE001
                delivery.status = "failed"
                delivery.error_message = str(exc)
                delivery.response_detail = {
                    "attempt": attempt,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
            await self._session.commit()
            if attempt < attempts:
                await asyncio.sleep(self.BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        return False

    def _build_alarm_payload(
        self,
        alarm: AlarmDefinition,
        event: AlarmFiringEvent,
    ) -> NotificationPayload:
        if event.resolved_at is not None:
            notification_type = NotificationType.ALARM_RESOLVED
            subject = f"Alarm resolved: {alarm.name}"
            body = "The alarm condition is no longer met."
        else:
            notification_type = NotificationType.ALARM_FIRING
            subject = f"Alarm firing: {alarm.name}"
            body = event.explanation or "Alarm condition met."
        return NotificationPayload(
            type=notification_type,
            subject=subject,
            body=body,
            alarm_id=str(alarm.id),
            explanation=event.explanation,
            metadata={
                "alarm_name": alarm.name,
                "alarm_explanation": event.explanation,
                "fired_at": event.fired_at.isoformat() if event.fired_at else None,
                "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
                "condition_snapshot": event.condition_snapshot,
                "context_snapshot": event.context_snapshot,
            },
        )


__all__ = ["NotifierDispatcher"]
