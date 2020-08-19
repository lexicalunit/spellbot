"""Adds user teams

Revision ID: be8afab17cbf
Revises: 95d86da7b3c7
Create Date: 2020-08-19 14:20:57.539270

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "be8afab17cbf"
down_revision = "95d86da7b3c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_teams",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )


def downgrade():
    op.drop_table("user_teams")
