"""Adds auto verification channel setting

Revision ID: 84903dda8911
Revises: 907102748ac5
Create Date: 2020-12-09 20:21:54.134287

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "84903dda8911"
down_revision = "907102748ac5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auto_verify_channels",
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_xid"),
    )
    op.create_index(
        op.f("ix_auto_verify_channels_guild_xid"),
        "auto_verify_channels",
        ["guild_xid"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_auto_verify_channels_guild_xid"), table_name="auto_verify_channels"
    )
    op.drop_table("auto_verify_channels")
