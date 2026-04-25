from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedJSON, EncryptedText


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("dedup_hash", name="uq_transactions_dedup_hash"),
        UniqueConstraint(
            "account_id",
            "provider_transaction_id",
            name="uq_transactions_account_provider_txn",
        ),
        Index("ix_transactions_card_id", "card_id"),
    )

    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    card_id: Mapped[str | None] = mapped_column(ForeignKey("cards.id"), nullable=True)
    provider_transaction_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    currency: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_category: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    description: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    merchant_category: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    transaction_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    settled_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    running_balance: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    dedup_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_recurring_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence_profile_id: Mapped[str | None] = mapped_column(nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


__all__ = ["Transaction"]
