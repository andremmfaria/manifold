from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedJSON, EncryptedText


class Balance(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "balances"

    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    card_id: Mapped[str | None] = mapped_column(ForeignKey("cards.id"), nullable=True, index=True)
    available: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    current: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    currency: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    overdraft: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


__all__ = ["Balance"]
