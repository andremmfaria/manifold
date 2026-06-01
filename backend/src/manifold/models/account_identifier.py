from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, UUIDPrimaryKeyMixin


class AccountIdentifier(UUIDPrimaryKeyMixin, Base):
    """One observed bank identifier (IBAN / SCAN / ABA) keyed to an AccountIdentity.

    Append-only: identifiers accumulate across syncs; never overwritten.
    retired_at non-null means this identifier is excluded from matching (§4.4).
    merged_from_identity records provenance when a merge re-pointed this row
    from another identity, enabling reversible unmerge (§13).
    """

    __tablename__ = "account_identifiers"
    __table_args__ = (
        CheckConstraint(
            "id_type IN ('iban', 'scan', 'aba')",
            name="ck_account_identifiers_id_type",
        ),
        UniqueConstraint(
            "user_id",
            "id_type",
            "value_hmac",
            "currency",
            name="uq_account_identifiers_user_type_hmac_currency",
        ),
    )

    identity_id: Mapped[str] = mapped_column(
        ForeignKey("account_identities.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # String(16): CHECK constraint limits to 'iban'|'scan'|'aba' (≤4 chars);
    # bounded so MariaDB can index without USING HASH fallback.
    id_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # HMAC-SHA256 hex is always exactly 64 chars; String(64) is precise and
    # avoids the MariaDB TEXT-in-key-without-prefix-length antipattern.
    value_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    # ISO 4217 currency codes are 3 chars; sentinel '-' is 1 char; String(8)
    # gives headroom and keeps this column indexable on all backends.
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Bumped every sync the identifier is still observed.
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Non-null = retired; excluded from matching (§4.4).
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Provenance: original identity this row belonged to before a merge re-pointed it.
    # Null = born in this identity.
    merged_from_identity: Mapped[str | None] = mapped_column(
        ForeignKey("account_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["AccountIdentifier"]
