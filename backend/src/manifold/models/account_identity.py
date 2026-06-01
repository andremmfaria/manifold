from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AccountIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stable internal node representing a single real-world bank account.

    Assigned once and never recomputed — identifiers accrete onto this node.
    merged_into/merged_at non-null means this identity is a tombstone absorbed
    into another (the survivor); kept for audit and reversible unmerge (§13).
    """

    __tablename__ = "account_identities"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Canonical display/metadata source; oldest member account by created_at.
    # Nullable until the first account is bound.
    master_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    # auto = formed by the sync engine; manual = formed by explicit user merge (§13).
    origin: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("origin IN ('auto', 'manual')", name="ck_account_identities_origin"),
        nullable=False,
        default="auto",
    )
    # Tombstone pointer: non-null means this identity was absorbed into the survivor.
    merged_into: Mapped[str | None] = mapped_column(
        ForeignKey("account_identities.id"), nullable=True
    )
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["AccountIdentity"]
