"""
Adds commander brackets.

Revision ID: d1fca945a660
Revises: 432249d9ddbc
Create Date: 2025-02-11 11:43:03.471989
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d1fca945a660"
down_revision = "432249d9ddbc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "default_bracket",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_channels_default_bracket"),
        "channels",
        ["default_bracket"],
        unique=False,
    )
    op.add_column(
        "games",
        sa.Column(
            "bracket",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_games_bracket"),
        "games",
        ["bracket"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_games_bracket"), table_name="games")
    op.drop_column("games", "bracket")
    op.drop_index(op.f("ix_channels_default_bracket"), table_name="channels")
    op.drop_column("channels", "default_bracket")
