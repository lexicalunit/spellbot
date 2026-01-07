"""
Add deleted_at to Notifications.

Revision ID: a53eae0a3e4a
Revises: bf1701e13fcd
Create Date: 2026-01-06 20:32:25.123836
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a53eae0a3e4a"
down_revision = "bf1701e13fcd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("notifications", "deleted_at")
