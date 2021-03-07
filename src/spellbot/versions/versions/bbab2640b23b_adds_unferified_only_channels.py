"""Adds unferified-only channels

Revision ID: bbab2640b23b
Revises: 83c728a2823e
Create Date: 2021-03-06 14:14:02.709635

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bbab2640b23b"
down_revision = "83c728a2823e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "unverified_only_channels",
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_xid"),
    )
    op.create_index(
        op.f("ix_unverified_only_channels_guild_xid"),
        "unverified_only_channels",
        ["guild_xid"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_unverified_only_channels_guild_xid"),
        table_name="unverified_only_channels",
    )
    op.drop_table("unverified_only_channels")
