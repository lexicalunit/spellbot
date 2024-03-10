"""
Adds an index on plays by game_id.

Revision ID: ef54f035a75c
Revises: 8b560fcec5f7
Create Date: 2021-11-26 22:40:31.045418

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "ef54f035a75c"
down_revision = "8b560fcec5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_plays_game_id"), "plays", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_plays_game_id"), table_name="plays")
