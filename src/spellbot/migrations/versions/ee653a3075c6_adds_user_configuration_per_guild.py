"""Adds user configuration per guild

Revision ID: ee653a3075c6
Revises: 7abc75daaa94
Create Date: 2021-11-18 11:44:25.588532

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ee653a3075c6"
down_revision = "7abc75daaa94"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "configs",
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("power_level", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_xid", "user_xid"),
    )


def downgrade():
    op.drop_table("configs")
