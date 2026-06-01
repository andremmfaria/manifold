"""Email subsystem tables

Adds:
  instance_email_settings  — per-instance SMTP/API provider config (encrypted)
  email_suppression        — hard-bounce / unsubscribe suppression list (HMAC-keyed)
  email_webhook_events     — raw inbound provider webhook events

Revision ID: 0007_email_subsystem
Revises: 0006_txn_dedup
Create Date: 2026-06-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_email_subsystem"
down_revision = "0006_txn_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── instance_email_settings ─────────────────────────────────────────────
    # One row per instance; config/from_address/from_name are EncryptedText /
    # EncryptedJSON at the ORM layer — they persist as LargeBinary in the DB.
    op.create_table(
        "instance_email_settings",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("config", sa.LargeBinary(), nullable=True),
        sa.Column("from_address", sa.LargeBinary(), nullable=True),
        sa.Column("from_name", sa.LargeBinary(), nullable=True),
        sa.Column(
            "is_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── email_suppression ───────────────────────────────────────────────────
    # address_hmac is HMAC-SHA256 of the normalised address; stored as
    # LargeBinary (bytes) so the unique constraint is a B-tree over raw bytes —
    # no BLOB-prefix-length problem on MariaDB because LargeBinary maps to
    # VARBINARY(n) when a length is inferred, and our HMAC is fixed-width.
    # Uniqueness is enforced by the named index below (unique=True) rather than
    # a column-level flag to avoid a duplicate-index conflict on PostgreSQL and
    # SQLite (both would otherwise create two unique indexes for the same column).
    op.create_table(
        "email_suppression",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("address_hmac", sa.LargeBinary(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_email_suppression_address_hmac",
        "email_suppression",
        ["address_hmac"],
        unique=True,
    )

    # ── email_webhook_events ────────────────────────────────────────────────
    # raw payload is EncryptedJSON at the ORM layer → LargeBinary here.
    op.create_table(
        "email_webhook_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("raw", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_email_webhook_events_provider_event_type",
        "email_webhook_events",
        ["provider", "event_type"],
    )


def downgrade() -> None:
    # Drop indexes before tables; reverse creation order.
    op.drop_index("ix_email_webhook_events_provider_event_type", table_name="email_webhook_events")
    op.drop_index("ix_email_suppression_address_hmac", table_name="email_suppression")

    op.drop_table("email_webhook_events")
    op.drop_table("email_suppression")
    op.drop_table("instance_email_settings")
