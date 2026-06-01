from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin


class EmailSuppression(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_suppression"

    address_hmac: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, unique=True, index=True
    )
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["EmailSuppression"]
