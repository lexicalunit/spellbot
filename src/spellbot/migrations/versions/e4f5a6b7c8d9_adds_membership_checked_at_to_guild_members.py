# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Adds membership_checked_at to guild_members.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-20 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Null means "never confirmed against Discord", which is what every existing row is,
    # so the first analytics view after this ships re-checks them and then goes quiet.
    op.add_column(
        "guild_members",
        sa.Column("membership_checked_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_members", "membership_checked_at")
