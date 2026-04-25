"""alarms notifiers and recurrence profiles

Revision ID: 0003_alarms_notifiers
Revises: 0002_data_in
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_alarms_notifiers"
down_revision = "0002_data_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifier_configs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.LargeBinary(), nullable=False),
        sa.Column("type", sa.LargeBinary(), nullable=False),
        sa.Column("config", sa.LargeBinary(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "recurrence_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("label", sa.LargeBinary(), nullable=True),
        sa.Column("merchant_pattern", sa.LargeBinary(), nullable=True),
        sa.Column("amount_mean", sa.LargeBinary(), nullable=True),
        sa.Column("amount_stddev", sa.LargeBinary(), nullable=True),
        sa.Column("cadence_days", sa.Integer(), nullable=True),
        sa.Column("cadence_stddev", sa.Numeric(6, 2), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_predicted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_predicted_amount", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "alarm_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.LargeBinary(), nullable=False),
        sa.Column("condition", sa.LargeBinary(), nullable=True),
        sa.Column("condition_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False),
        sa.Column("for_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("notify_on_resolve", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "alarm_states",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_definitions.id"),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("mute_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_true", sa.Integer(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("alarm_id", name="uq_alarm_states_alarm_id"),
    )

    op.create_table(
        "alarm_evaluation_results",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_definitions.id"),
            nullable=False,
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.Boolean(), nullable=False),
        sa.Column("previous_state", sa.Text(), nullable=True),
        sa.Column("new_state", sa.Text(), nullable=True),
        sa.Column("condition_version", sa.Integer(), nullable=True),
        sa.Column("context_snapshot", sa.LargeBinary(), nullable=True),
        sa.Column("explanation", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "alarm_firing_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_definitions.id"),
            nullable=False,
        ),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("explanation", sa.LargeBinary(), nullable=True),
        sa.Column("condition_snapshot", sa.LargeBinary(), nullable=True),
        sa.Column("context_snapshot", sa.LargeBinary(), nullable=True),
        sa.Column("notifications_sent", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "alarm_account_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_definitions.id"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("alarm_id", "account_id", name="uq_alarm_account_assignments_pair"),
    )

    op.create_table(
        "alarm_notifier_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_definitions.id"),
            nullable=False,
        ),
        sa.Column(
            "notifier_id",
            sa.String(length=36),
            sa.ForeignKey("notifier_configs.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "alarm_id",
            "notifier_id",
            name="uq_alarm_notifier_assignments_pair",
        ),
    )

    op.create_table(
        "alarm_definition_versions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_definition_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_definitions.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("condition", sa.LargeBinary(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "alarm_definition_id",
            "version",
            name="uq_alarm_definition_versions_definition_version",
        ),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "alarm_firing_event_id",
            sa.String(length=36),
            sa.ForeignKey("alarm_firing_events.id"),
            nullable=True,
        ),
        sa.Column(
            "notifier_id",
            sa.String(length=36),
            sa.ForeignKey("notifier_configs.id"),
            nullable=True,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("rendered_subject", sa.LargeBinary(), nullable=True),
        sa.Column("rendered_body", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_payload", sa.LargeBinary(), nullable=True),
        sa.Column("response_detail", sa.LargeBinary(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    with op.batch_alter_table("transactions") as batch_op:
        batch_op.create_foreign_key(
            "fk_transactions_recurrence_profile_id_recurrence_profiles",
            "recurrence_profiles",
            ["recurrence_profile_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint(
            "fk_transactions_recurrence_profile_id_recurrence_profiles",
            type_="foreignkey",
        )

    op.drop_table("notification_deliveries")
    op.drop_table("alarm_definition_versions")
    op.drop_table("alarm_notifier_assignments")
    op.drop_table("alarm_account_assignments")
    op.drop_table("alarm_firing_events")
    op.drop_table("alarm_evaluation_results")
    op.drop_table("alarm_states")
    op.drop_table("alarm_definitions")
    op.drop_table("recurrence_profiles")
    op.drop_table("notifier_configs")
