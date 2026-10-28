# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Adds the Convoke guild call to action.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-28 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

from spellbot import audit

# revision identifiers, used by Alembic.
revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "show_convoke_guild",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column("games", sa.Column("convoke_guild_name", sa.String(length=128), nullable=True))
    op.add_column("games", sa.Column("convoke_guild_url", sa.String(length=255), nullable=True))
    audit.attach_triggers(op.get_bind())


def downgrade() -> None:
    op.drop_column("games", "convoke_guild_url")
    op.drop_column("games", "convoke_guild_name")
    op.drop_column("guilds", "show_convoke_guild")
    audit.attach_triggers(op.get_bind())
