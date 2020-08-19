"""Adds teams

Revision ID: 95d86da7b3c7
Revises: b887e657fb80
Create Date: 2020-08-19 12:41:00.320532

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "95d86da7b3c7"
down_revision = "b887e657fb80"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_teams_guild_xid"), "teams", ["guild_xid"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_teams_guild_xid"), table_name="teams")
    op.drop_table("teams")
