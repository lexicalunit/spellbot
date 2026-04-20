"""
Add composite index for inactive_games query.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-20 12:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create composite index to optimize the inactive_games query which filters by
    # status and deleted_at, then uses HAVING with updated_at
    op.create_index(
        "ix_games_status_deleted_at_updated_at",
        "games",
        ["status", "deleted_at", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_games_status_deleted_at_updated_at", table_name="games")
