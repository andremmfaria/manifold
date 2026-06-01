"""account identity tables and accounts.identity_id

Revision ID: 0005_account_identity
Revises: 0004_user_names
Create Date: 2026-06-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_account_identity"
down_revision = "0004_user_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── account_identities ──────────────────────────────────────────────────
    # All FKs (including self-FK merged_into and master_account_id → accounts)
    # are declared inline in create_table so they work on SQLite without ALTER.
    op.create_table(
        "account_identities",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "master_account_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id"),
            nullable=True,
        ),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column(
            "merged_into",
            sa.String(length=36),
            sa.ForeignKey("account_identities.id"),
            nullable=True,
        ),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("origin IN ('auto', 'manual')", name="ck_account_identities_origin"),
    )
    op.create_index("ix_account_identities_user_id", "account_identities", ["user_id"])

    # ── account_identifiers ─────────────────────────────────────────────────
    op.create_table(
        "account_identifiers",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "identity_id",
            sa.String(length=36),
            sa.ForeignKey("account_identities.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        # String bounds keep these columns indexable on MariaDB without the
        # BLOB/TEXT-in-key-without-prefix-length error (or silent USING HASH
        # fallback in MariaDB 10.5+).  id_type: CHECK limits to ≤4-char values
        # but 16 gives room for future types.  value_hmac: HMAC-SHA256 hex is
        # always exactly 64 chars.  currency: ISO 4217 is 3 chars; sentinel
        # '-' is 1 char; 8 gives headroom.
        sa.Column("id_type", sa.String(length=16), nullable=False),
        sa.Column("value_hmac", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "merged_from_identity",
            sa.String(length=36),
            sa.ForeignKey("account_identities.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "id_type IN ('iban', 'scan', 'aba')",
            name="ck_account_identifiers_id_type",
        ),
        sa.UniqueConstraint(
            "user_id",
            "id_type",
            "value_hmac",
            "currency",
            name="uq_account_identifiers_user_type_hmac_currency",
        ),
    )
    op.create_index("ix_account_identifiers_identity_id", "account_identifiers", ["identity_id"])
    op.create_index("ix_account_identifiers_user_id", "account_identifiers", ["user_id"])

    # ── account_identity_assertions ─────────────────────────────────────────
    op.create_table(
        "account_identity_assertions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "account_a_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column(
            "account_b_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('same', 'do_not_merge')",
            name="ck_account_identity_assertions_kind",
        ),
    )
    op.create_index(
        "ix_account_identity_assertions_user_id",
        "account_identity_assertions",
        ["user_id"],
    )
    op.create_index(
        "ix_account_identity_assertions_account_a_id",
        "account_identity_assertions",
        ["account_a_id"],
    )
    op.create_index(
        "ix_account_identity_assertions_account_b_id",
        "account_identity_assertions",
        ["account_b_id"],
    )

    # ── accounts.identity_id (nullable FK) ──────────────────────────────────
    # uq_accounts_provider_account is intentionally untouched.
    # batch_alter_table is used for the column addition; in SQLite batch mode
    # the copy-and-move strategy handles the FK transparently on a live DB.
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("identity_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_accounts_identity_id", ["identity_id"])
        batch_op.create_foreign_key(
            "fk_accounts_identity_id",
            "account_identities",
            ["identity_id"],
            ["id"],
        )


def downgrade() -> None:
    # Remove accounts.identity_id first (child FK).
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint("fk_accounts_identity_id", type_="foreignkey")
        batch_op.drop_index("ix_accounts_identity_id")
        batch_op.drop_column("identity_id")

    # Drop account_identity_assertions (no deps on new tables).
    # Indexes are dropped with the table — dropping them first via op.drop_index
    # would fail on MariaDB because named indexes that back FK constraints
    # cannot be dropped independently while the FK still exists.
    op.drop_table("account_identity_assertions")

    # Drop account_identifiers (all FKs and indexes dropped with the table).
    op.drop_table("account_identifiers")

    # Drop account_identities last (referenced by account_identifiers above).
    # All FKs and indexes dropped with the table.
    op.drop_table("account_identities")
