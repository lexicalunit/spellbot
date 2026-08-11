# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Adds Convoke Guild War fields to games.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-04 16:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("war_id", sa.String(length=36), nullable=True))
    op.add_column("games", sa.Column("war_title", sa.String(length=160), nullable=True))
    op.create_index(op.f("ix_games_war_id"), "games", ["war_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_war_id"), table_name="games")
    op.drop_column("games", "war_title")
    op.drop_column("games", "war_id")
