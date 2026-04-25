from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedJSON, EncryptedText


class ProviderConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_connections"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    display_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="inactive")
    auth_status: Mapped[str] = mapped_column(Text, nullable=False, default="connected")
    credentials_encrypted: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    config: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    consent_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


__all__ = ["ProviderConnection"]
