"""data in milestone tables

Revision ID: 0002_data_in
Revises: 0001_initial
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_data_in"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_type", sa.LargeBinary(), nullable=False),
        sa.Column("display_name", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("auth_status", sa.Text(), nullable=False),
        sa.Column("credentials_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("config", sa.LargeBinary(), nullable=True),
        sa.Column("consent_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_connections_user_id", "provider_connections", ["user_id"])

    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "provider_connection_id",
            sa.String(length=36),
            sa.ForeignKey("provider_connections.id"),
            nullable=False,
        ),
        sa.Column("provider_account_id", sa.Text(), nullable=False),
        sa.Column("account_type", sa.LargeBinary(), nullable=False),
        sa.Column("currency", sa.LargeBinary(), nullable=False),
        sa.Column("display_name", sa.LargeBinary(), nullable=True),
        sa.Column("iban", sa.LargeBinary(), nullable=True),
        sa.Column("sort_code", sa.LargeBinary(), nullable=True),
        sa.Column("account_number", sa.LargeBinary(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider_connection_id", "provider_account_id", name="uq_accounts_provider_account"
        ),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    op.create_index("ix_accounts_provider_connection_id", "accounts", ["provider_connection_id"])

    op.create_table(
        "cards",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "provider_connection_id",
            sa.String(length=36),
            sa.ForeignKey("provider_connections.id"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("provider_card_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.LargeBinary(), nullable=True),
        sa.Column("card_network", sa.Text(), nullable=True),
        sa.Column("partial_card_number", sa.LargeBinary(), nullable=True),
        sa.Column("currency", sa.LargeBinary(), nullable=True),
        sa.Column("credit_limit", sa.LargeBinary(), nullable=True),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_connection_id", "provider_card_id", name="uq_cards_provider_card"),
    )
    op.create_index("ix_cards_provider_connection_id", "cards", ["provider_connection_id"])
    op.create_index("ix_cards_account_id", "cards", ["account_id"])

    op.create_table(
        "balances",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("card_id", sa.String(length=36), sa.ForeignKey("cards.id"), nullable=True),
        sa.Column("available", sa.LargeBinary(), nullable=True),
        sa.Column("current", sa.LargeBinary(), nullable=True),
        sa.Column("currency", sa.LargeBinary(), nullable=True),
        sa.Column("overdraft", sa.LargeBinary(), nullable=True),
        sa.Column("credit_limit", sa.LargeBinary(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
    )
    op.create_index("ix_balances_account_id", "balances", ["account_id"])
    op.create_index("ix_balances_card_id", "balances", ["card_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("card_id", sa.String(length=36), sa.ForeignKey("cards.id"), nullable=True),
        sa.Column("provider_transaction_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("amount", sa.LargeBinary(), nullable=True),
        sa.Column("currency", sa.LargeBinary(), nullable=True),
        sa.Column("transaction_type", sa.Text(), nullable=True),
        sa.Column("transaction_category", sa.LargeBinary(), nullable=True),
        sa.Column("description", sa.LargeBinary(), nullable=True),
        sa.Column("merchant_name", sa.LargeBinary(), nullable=True),
        sa.Column("merchant_category", sa.LargeBinary(), nullable=True),
        sa.Column("transaction_date", sa.LargeBinary(), nullable=True),
        sa.Column("settled_date", sa.LargeBinary(), nullable=True),
        sa.Column("running_balance", sa.LargeBinary(), nullable=True),
        sa.Column("dedup_hash", sa.Text(), nullable=False),
        sa.Column("is_recurring_candidate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recurrence_profile_id", sa.String(length=36), nullable=True),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dedup_hash", name="uq_transactions_dedup_hash"),
        sa.UniqueConstraint(
            "account_id",
            "provider_transaction_id",
            name="uq_transactions_account_provider_txn",
        ),
    )
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_card_id", "transactions", ["card_id"])

    op.create_table(
        "pending_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("provider_transaction_id", sa.Text(), nullable=True),
        sa.Column("amount", sa.LargeBinary(), nullable=True),
        sa.Column("currency", sa.LargeBinary(), nullable=True),
        sa.Column("description", sa.LargeBinary(), nullable=True),
        sa.Column("merchant_name", sa.LargeBinary(), nullable=True),
        sa.Column("transaction_date", sa.LargeBinary(), nullable=True),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pending_transactions_account_id", "pending_transactions", ["account_id"])

    op.create_table(
        "direct_debits",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("provider_mandate_id", sa.Text(), nullable=True),
        sa.Column("name", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("amount", sa.LargeBinary(), nullable=True),
        sa.Column("currency", sa.LargeBinary(), nullable=True),
        sa.Column("frequency", sa.Text(), nullable=True),
        sa.Column("reference", sa.LargeBinary(), nullable=True),
        sa.Column("last_payment_date", sa.LargeBinary(), nullable=True),
        sa.Column("next_payment_date", sa.LargeBinary(), nullable=True),
        sa.Column("next_payment_amount", sa.LargeBinary(), nullable=True),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "account_id",
            "provider_mandate_id",
            name="uq_direct_debits_account_provider_mandate",
        ),
    )
    op.create_index("ix_direct_debits_account_id", "direct_debits", ["account_id"])

    op.create_table(
        "standing_orders",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("provider_standing_order_id", sa.Text(), nullable=True),
        sa.Column("reference", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("currency", sa.LargeBinary(), nullable=True),
        sa.Column("frequency", sa.Text(), nullable=True),
        sa.Column("first_payment_date", sa.LargeBinary(), nullable=True),
        sa.Column("first_payment_amount", sa.LargeBinary(), nullable=True),
        sa.Column("next_payment_date", sa.LargeBinary(), nullable=True),
        sa.Column("next_payment_amount", sa.LargeBinary(), nullable=True),
        sa.Column("final_payment_date", sa.LargeBinary(), nullable=True),
        sa.Column("final_payment_amount", sa.LargeBinary(), nullable=True),
        sa.Column("previous_payment_date", sa.LargeBinary(), nullable=True),
        sa.Column("previous_payment_amount", sa.LargeBinary(), nullable=True),
        sa.Column("raw_payload", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "account_id",
            "provider_standing_order_id",
            name="uq_standing_orders_account_provider_order",
        ),
    )
    op.create_index("ix_standing_orders_account_id", "standing_orders", ["account_id"])

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "provider_connection_id",
            sa.String(length=36),
            sa.ForeignKey("provider_connections.id"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accounts_synced", sa.Integer(), nullable=True),
        sa.Column("transactions_synced", sa.Integer(), nullable=True),
        sa.Column("new_transactions", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_runs_provider_connection_id", "sync_runs", ["provider_connection_id"])
    op.create_index("ix_sync_runs_account_id", "sync_runs", ["account_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("explanation", sa.LargeBinary(), nullable=True),
    )
    op.create_index("ix_events_account_id", "events", ["account_id"])
    op.create_index("ix_events_user_id", "events", ["user_id"])

    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("state", sa.Text(), nullable=False, unique=True),
        sa.Column("provider_type", sa.Text(), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(length=36),
            sa.ForeignKey("provider_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_states_connection_id", "oauth_states", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_states_connection_id", table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_events_user_id", table_name="events")
    op.drop_index("ix_events_account_id", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_sync_runs_account_id", table_name="sync_runs")
    op.drop_index("ix_sync_runs_provider_connection_id", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_index("ix_standing_orders_account_id", table_name="standing_orders")
    op.drop_table("standing_orders")
    op.drop_index("ix_direct_debits_account_id", table_name="direct_debits")
    op.drop_table("direct_debits")
    op.drop_index("ix_pending_transactions_account_id", table_name="pending_transactions")
    op.drop_table("pending_transactions")
    op.drop_index("ix_transactions_card_id", table_name="transactions")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_balances_card_id", table_name="balances")
    op.drop_index("ix_balances_account_id", table_name="balances")
    op.drop_table("balances")
    op.drop_index("ix_cards_account_id", table_name="cards")
    op.drop_index("ix_cards_provider_connection_id", table_name="cards")
    op.drop_table("cards")
    op.drop_index("ix_accounts_provider_connection_id", table_name="accounts")
    op.drop_index("ix_accounts_user_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_index("ix_provider_connections_user_id", table_name="provider_connections")
    op.drop_table("provider_connections")
