"""
Soft delete alerts.

Revision ID: 2dcac4a84d45
Revises: 26b7c8d9e0f1
Create Date: 2026-06-03 23:01:04.613761
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2dcac4a84d45"
down_revision = "26b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_alerts_deleted_at"), "alerts", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alerts_deleted_at"), table_name="alerts")
    op.drop_column("alerts", "deleted_at")
