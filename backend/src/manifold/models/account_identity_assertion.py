from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin


class AccountIdentityAssertion(UUIDPrimaryKeyMixin, Base):
    """User assertion about the relationship between two Account rows.

    'same'         — user pins two accounts as identical even without shared identifiers.
    'do_not_merge' — user explicitly separated two accounts; blocks auto-merge (§3.1 step 0).

    Stored at account-pair level (not identity level) so assertions survive identity churn.
    Used in Phase 6 (manual merge/unmerge UI); created now so the schema is complete.
    """

    __tablename__ = "account_identity_assertions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('same', 'do_not_merge')",
            name="ck_account_identity_assertions_kind",
        ),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    account_a_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    account_b_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["AccountIdentityAssertion"]
