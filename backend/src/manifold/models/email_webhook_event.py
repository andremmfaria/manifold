from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedJSON


class EmailWebhookEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_webhook_events"

    __table_args__ = (
        Index("ix_email_webhook_events_provider_event_type", "provider", "event_type"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    raw: Mapped[object] = mapped_column(EncryptedJSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["EmailWebhookEvent"]
