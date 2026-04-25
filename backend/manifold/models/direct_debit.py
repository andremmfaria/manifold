from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedJSON, EncryptedText


class DirectDebit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "direct_debits"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "provider_mandate_id",
            name="uq_direct_debits_account_provider_mandate",
        ),
        Index("ix_direct_debits_account_id", "account_id"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    provider_mandate_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    currency: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    last_payment_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    next_payment_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    next_payment_amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


__all__ = ["DirectDebit"]
