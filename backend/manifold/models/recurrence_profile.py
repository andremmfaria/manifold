from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedText


class RecurrenceProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurrence_profiles"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    merchant_pattern: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    amount_mean: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    amount_stddev: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    cadence_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadence_stddev: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_predicted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_predicted_amount: Mapped[Decimal | None] = mapped_column(
        EncryptedDecimal(), nullable=True
    )
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_source: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["RecurrenceProfile"]
