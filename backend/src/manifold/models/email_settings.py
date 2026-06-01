from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin
from manifold.security.types import EncryptedJSON, EncryptedText


class InstanceEmailSettings(TimestampMixin, Base):
    __tablename__ = "instance_email_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[object] = mapped_column(EncryptedJSON(), nullable=True)
    from_address: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    from_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    is_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


__all__ = ["InstanceEmailSettings"]
