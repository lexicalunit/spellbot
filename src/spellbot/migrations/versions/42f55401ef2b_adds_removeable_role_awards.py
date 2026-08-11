# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Adds removeable role awards.

Revision ID: 42f55401ef2b
Revises: 6e982c9318a6
Create Date: 2021-12-31 17:50:24.259796

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "42f55401ef2b"
down_revision = "6e982c9318a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_awards",
        sa.Column(
            "remove",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_awards", "remove")
