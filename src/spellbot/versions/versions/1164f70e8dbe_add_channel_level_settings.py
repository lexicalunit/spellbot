"""Add channel level settings

Revision ID: 1164f70e8dbe
Revises: 6c1db37e135b
Create Date: 2020-11-05 11:12:38.749248

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1164f70e8dbe"
down_revision = "6c1db37e135b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "channel_settings",
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("default_size", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_xid"),
    )
    op.create_index(
        op.f("ix_channel_settings_guild_xid"),
        "channel_settings",
        ["guild_xid"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_channel_settings_guild_xid"), table_name="channel_settings")
    op.drop_table("channel_settings")
