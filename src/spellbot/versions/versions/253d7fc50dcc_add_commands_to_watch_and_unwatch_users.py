"""Add commands to watch and unwatch users

Revision ID: 253d7fc50dcc
Revises: bf9689a382b3
Create Date: 2021-02-19 14:27:35.586190

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "253d7fc50dcc"
down_revision = "bf9689a382b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "watched_users",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )


def downgrade():
    op.drop_table("watched_users")
