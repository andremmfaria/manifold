from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedJSON, EncryptedText


class NotifierConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifier_configs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    type: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    config: Mapped[object] = mapped_column(EncryptedJSON(), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


__all__ = ["NotifierConfig"]
