from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
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
        # Phase 5 — identity-scoped dedup key (Tier 1).
        # String(64) not Text: unique constraint on MariaDB requires bounded type
        # (TEXT in a UNIQUE index fails or silently degrades to USING HASH).
        # NULL rows are excluded from uniqueness on all three backends (SQL standard).
        UniqueConstraint("identity_dedup_hash", name="uq_transactions_identity_dedup_hash"),
        Index("ix_transactions_card_id", "card_id"),
        Index("ix_transactions_content_hash", "content_hash"),
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
    # --- Phase 5: cross-connection dedup columns ---
    # Tier 1: HMAC(manifold-txn-dedup, identity_id + ':' + normalized_provider_txn_id).
    # Null when account.identity_id is null (unresolved accounts use legacy dedup_hash).
    # String(64) = HMAC-SHA256 hex length; bounded for MariaDB UNIQUE index.
    identity_dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Tier 2: HMAC(manifold-txn-content, identity_id + ':' + amount + ':' + date + ':' + desc).
    # Computed from decrypted values at sync time; null when inputs are ineligible.
    # NOT in a unique constraint — only a lookup key; Tier 2 is opt-in per identity pair.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Soft-delete flag set by the backfill when this row is identified as a
    # cross-connection duplicate of a row already stored under the canonical
    # (oldest) account for the same identity.  Read-time aggregation filters
    # WHERE is_cross_connection_duplicate = FALSE to avoid double-counting.
    # Phase 5d backfill writes this; sync engine never sets it directly.
    is_cross_connection_duplicate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


__all__ = ["Transaction"]
