"""
Adds support for blind games.

Revision ID: 7a81bb6dfb9a
Revises: 6e5dbb20dd86
Create Date: 2025-08-12 09:00:22.853992
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7a81bb6dfb9a"
down_revision = "6e5dbb20dd86"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("blind", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "channels",
        sa.Column("blind_games", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("channels", "blind_games")
    op.drop_column("games", "blind")
