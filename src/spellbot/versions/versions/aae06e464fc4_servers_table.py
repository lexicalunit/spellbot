"""Servers table

Revision ID: aae06e464fc4
Revises: 2ad0a1c189cc
Create Date: 2020-07-03 13:44:21.203939

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "aae06e464fc4"
down_revision = "2ad0a1c189cc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("prefix", sa.String(length=10), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_table("bot_prefixes")


def downgrade():
    op.create_table(
        "bot_prefixes",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("guild_xid", sa.BIGINT(), nullable=False),
        sa.Column("prefix", sa.VARCHAR(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_table("servers")
