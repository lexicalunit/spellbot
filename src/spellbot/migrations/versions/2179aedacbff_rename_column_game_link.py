"""
Rename column game_link.

Revision ID: 2179aedacbff
Revises: 7a81bb6dfb9a
Create Date: 2025-09-21 17:13:45.958072
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "2179aedacbff"
down_revision = "7a81bb6dfb9a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("games", "spelltable_link", new_column_name="game_link")


def downgrade() -> None:
    op.alter_column("games", "game_link", new_column_name="spelltable_link")
