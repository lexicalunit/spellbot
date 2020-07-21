"""Refactor channels table

Revision ID: b8bf94efa410
Revises: 18b8b53f9202
Create Date: 2020-07-20 18:23:01.039729

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b8bf94efa410"
down_revision = "18b8b53f9202"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "channels",
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_xid"),
    )
    op.drop_table("authorized_channels")


def downgrade():
    op.create_table(
        "authorized_channels",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("guild_xid", sa.BIGINT(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=100), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_table("channels")
