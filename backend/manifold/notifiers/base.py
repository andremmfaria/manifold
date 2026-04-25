from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NotificationType(str, Enum):  # noqa: UP042
    ALARM_FIRING = "alarm_firing"
    ALARM_RESOLVED = "alarm_resolved"
    SYSTEM_EVENT = "system_event"
    INFORMATIONAL = "informational"
    TEST = "test"


@dataclass
class NotificationPayload:
    type: NotificationType
    subject: str
    body: str
    alarm_id: str | None = None
    explanation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.type, str):
            self.type = NotificationType(self.type)
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PreparedNotification:
    subject: str
    body: str
    request_payload: dict[str, Any]


class BaseNotifier(ABC):
    notifier_type: str

    def prepare(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
    ) -> PreparedNotification:
        return PreparedNotification(
            subject=payload.subject,
            body=payload.body,
            request_payload=self.build_request_payload(
                payload,
                config,
                payload.subject,
                payload.body,
            ),
        )

    def build_request_payload(
        self,
        payload: NotificationPayload,
        config: dict[str, Any],
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        return {
            "type": payload.type.value,
            "subject": subject,
            "body": body,
            "metadata": dict(payload.metadata),
        }

    @abstractmethod
    async def send(self, payload: NotificationPayload, config: dict[str, Any]) -> bool: ...

    @abstractmethod
    async def test(self, config: dict[str, Any]) -> bool: ...

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> list[str]: ...


__all__ = [
    "BaseNotifier",
    "NotificationPayload",
    "NotificationType",
    "PreparedNotification",
]
