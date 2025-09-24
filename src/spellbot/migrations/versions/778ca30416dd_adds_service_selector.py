"""
Adds service selector.

Revision ID: 778ca30416dd
Revises: ea8f33717a54
Create Date: 2024-03-15 19:09:06.243556

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "778ca30416dd"
down_revision = "ea8f33717a54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("default_service", sa.Integer(), server_default=sa.text("2"), nullable=False),
    )
    op.create_index(
        op.f("ix_channels_default_service"),
        "channels",
        ["default_service"],
        unique=False,
    )
    op.add_column(
        "games",
        sa.Column("service", sa.Integer(), server_default=sa.text("2"), nullable=False),
    )
    op.create_index(op.f("ix_games_service"), "games", ["service"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_service"), table_name="games")
    op.drop_column("games", "service")
    op.drop_index(op.f("ix_channels_default_service"), table_name="channels")
    op.drop_column("channels", "default_service")
