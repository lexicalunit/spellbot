"""
Adds notified_at column to games table.

Revision ID: 26b7c8d9e0f1
Revises: 15a6b7c8d9e0
Create Date: 2026-05-30 16:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "26b7c8d9e0f1"
down_revision = "15a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("notified_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_games_notified_at", "games", ["notified_at"])


def downgrade() -> None:
    op.drop_index("ix_games_notified_at", table_name="games")
    op.drop_column("games", "notified_at")
