# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Remove watches.

Revision ID: a7b8c9d0e1f2
Revises: e4f5a6b7c8d9
Create Date: 2026-10-05 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Watch notifications DM'd every member of the mod role, which needs the privileged
    # Server Members intent to enumerate. SpellBot no longer requests it, so the feature is gone.
    op.drop_table("watches")


def downgrade() -> None:
    op.create_table(
        "watches",
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_xid", "user_xid"),
    )
