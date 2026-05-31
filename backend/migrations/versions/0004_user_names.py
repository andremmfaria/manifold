"""add first_name and last_name to users

Revision ID: 0004_user_names
Revises: 0003_alarms_notifiers
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_user_names"
down_revision = "0003_alarms_notifiers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("first_name", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_name", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")
