"""
Adds optional additional rules to games.

Revision ID: 6e5dbb20dd86
Revises: 3a2194f29016
Create Date: 2025-07-02 16:43:19.368371
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6e5dbb20dd86"
down_revision = "3a2194f29016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("rules", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_games_rules"), "games", ["rules"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_rules"), table_name="games")
    op.drop_column("games", "rules")
