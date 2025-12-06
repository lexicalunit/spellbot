"""
Add message id tracking to Notification.

Revision ID: 72d381e804b4
Revises: 7af4acbe6787
Create Date: 2025-12-06 10:02:04.359778
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "72d381e804b4"
down_revision = "7af4acbe6787"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("message", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_notifications_message"), "notifications", ["message"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_message"), table_name="notifications")
    op.drop_column("notifications", "message")
