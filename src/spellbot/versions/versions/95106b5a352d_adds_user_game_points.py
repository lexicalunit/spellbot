"""Adds user game points

Revision ID: 95106b5a352d
Revises: be8afab17cbf
Create Date: 2020-08-19 16:22:02.801830

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "95106b5a352d"
down_revision = "be8afab17cbf"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_points",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid", "game_id"),
    )


def downgrade():
    op.drop_table("user_points")
