from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedJSON, EncryptedText


class PendingTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "pending_transactions"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    currency: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    description: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    transaction_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


__all__ = ["PendingTransaction"]
