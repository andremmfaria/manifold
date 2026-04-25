from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedJSON, EncryptedText


class StandingOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standing_orders"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "provider_standing_order_id",
            name="uq_standing_orders_account_provider_order",
        ),
        Index("ix_standing_orders_account_id", "account_id"),
    )

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    provider_standing_order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_payment_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    first_payment_amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    next_payment_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    next_payment_amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    final_payment_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    final_payment_amount: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    previous_payment_date: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    previous_payment_amount: Mapped[Decimal | None] = mapped_column(
        EncryptedDecimal(), nullable=True
    )
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


__all__ = ["StandingOrder"]
