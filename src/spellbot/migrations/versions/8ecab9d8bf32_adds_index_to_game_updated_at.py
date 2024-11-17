"""
Adds index to game updated_at.

Revision ID: 8ecab9d8bf32
Revises: ecd365d590a3
Create Date: 2024-11-17 10:36:34.696600
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8ecab9d8bf32"
down_revision = "ecd365d590a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_games_updated_at"), "games", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_updated_at"), table_name="games")
