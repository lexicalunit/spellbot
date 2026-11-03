# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Adds to_mode and competitive_mode to games.

These snapshot the channel's settings when each game is created, so the admin dashboard can
chart their adoption over time the same way it does for blind games.

Revision ID: 1553b5dd225d
Revises: f8deb800833f
Create Date: 2026-11-03 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1553b5dd225d"
down_revision = "f8deb800833f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("to_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "games",
        sa.Column("competitive_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("games", "competitive_mode")
    op.drop_column("games", "to_mode")
