"""
Remove mirrors cruft.

Revision ID: 993303923867
Revises: 8ecab9d8bf32
Create Date: 2024-11-17 11:38:26.520662
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "993303923867"
down_revision = "8ecab9d8bf32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("mirrors")


def downgrade() -> None:
    op.create_table(
        "mirrors",
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("(now() AT TIME ZONE 'utc'::text)"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("(now() AT TIME ZONE 'utc'::text)"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("from_guild_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("from_channel_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("to_guild_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("to_channel_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["from_channel_xid"],
            ["channels.xid"],
            name="mirrors_from_channel_xid_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_guild_xid"],
            ["guilds.xid"],
            name="mirrors_from_guild_xid_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_channel_xid"],
            ["channels.xid"],
            name="mirrors_to_channel_xid_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_guild_xid"],
            ["guilds.xid"],
            name="mirrors_to_guild_xid_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "from_guild_xid",
            "from_channel_xid",
            "to_guild_xid",
            "to_channel_xid",
            name="mirrors_pkey",
        ),
    )
