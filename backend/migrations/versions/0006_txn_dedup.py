"""Phase 5 — transaction cross-connection dedup columns

Adds:
  transactions.identity_dedup_hash  String(64) NULL + UNIQUE (Tier 1 key)
  transactions.content_hash         String(64) NULL + index  (Tier 2 key, not unique)
  transactions.is_cross_connection_duplicate  Boolean NOT NULL DEFAULT FALSE

Existing constraints (uq_transactions_dedup_hash, uq_transactions_account_provider_txn)
are kept intact; the new unique constraint replaces neither — it is the identity-scoped
dedup key for accounts that have been matched to an AccountIdentity (Phase 3).

Down: drop the three columns (and the unique constraint + index that go with them).

Revision ID: 0006_txn_dedup
Revises: 0005_account_identity
Create Date: 2026-06-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_txn_dedup"
down_revision = "0005_account_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        # Tier 1 — identity-scoped HMAC; String(64) so the UNIQUE index is
        # a plain B-tree on all backends (MariaDB rejects TEXT in a unique key
        # without a prefix length, or silently builds a USING HASH index).
        batch_op.add_column(sa.Column("identity_dedup_hash", sa.String(64), nullable=True))
        # Tier 2 — content hash; not unique, just a lookup column.
        batch_op.add_column(sa.Column("content_hash", sa.String(64), nullable=True))
        # Soft-delete flag for the Phase 5d backfill.
        batch_op.add_column(
            sa.Column(
                "is_cross_connection_duplicate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        # Unique constraint on identity_dedup_hash — NULL rows are excluded on
        # all three backends (SQL:2003 §4.15.2: two NULLs are not equal for
        # UNIQUE purposes on PostgreSQL and SQLite; MariaDB behaves the same).
        batch_op.create_unique_constraint(
            "uq_transactions_identity_dedup_hash",
            ["identity_dedup_hash"],
        )
        # Non-unique index on content_hash for Tier 2 lookups.
        batch_op.create_index("ix_transactions_content_hash", ["content_hash"])


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_index("ix_transactions_content_hash")
        batch_op.drop_constraint("uq_transactions_identity_dedup_hash", type_="unique")
        batch_op.drop_column("is_cross_connection_duplicate")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("identity_dedup_hash")
