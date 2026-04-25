from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedJSON, EncryptedText


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider_connection_id",
            "provider_account_id",
            name="uq_accounts_provider_account",
        ),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider_connection_id: Mapped[str] = mapped_column(
        ForeignKey("provider_connections.id"), nullable=False, index=True
    )
    provider_account_id: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    currency: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    display_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    iban: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    sort_code: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    account_number: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


__all__ = ["Account"]
