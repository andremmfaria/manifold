from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedDecimal, EncryptedJSON, EncryptedText


class Card(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint(
            "provider_connection_id",
            "provider_card_id",
            name="uq_cards_provider_card",
        ),
    )

    provider_connection_id: Mapped[str] = mapped_column(
        ForeignKey("provider_connections.id"), nullable=False, index=True
    )
    account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True, index=True
    )
    provider_card_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    card_network: Mapped[str | None] = mapped_column(Text, nullable=True)
    partial_card_number: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    currency: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(EncryptedDecimal(), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


__all__ = ["Card"]
