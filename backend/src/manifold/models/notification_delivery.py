from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedJSON, EncryptedText


class NotificationDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_deliveries"

    alarm_firing_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("alarm_firing_events.id"), nullable=True
    )
    notifier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("notifier_configs.id"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rendered_subject: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    rendered_body: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    first_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_payload: Mapped[object | None] = mapped_column(EncryptedJSON(), nullable=True)
    response_detail: Mapped[object | None] = mapped_column(EncryptedJSON(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["NotificationDelivery"]
