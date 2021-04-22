"""Adds user award tracking

Revision ID: 87317566b389
Revises: 48be08d645a6
Create Date: 2021-04-21 17:31:43.613732

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "87317566b389"
down_revision = "48be08d645a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_awards",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("current_award_id", sa.Integer(), nullable=True),
        sa.Column("plays", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )
    op.create_index(
        op.f("ix_user_awards_guild_xid"), "user_awards", ["guild_xid"], unique=False
    )
    op.create_index(
        op.f("ix_user_awards_user_xid"), "user_awards", ["user_xid"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_user_awards_user_xid"), table_name="user_awards")
    op.drop_index(op.f("ix_user_awards_guild_xid"), table_name="user_awards")
    op.drop_table("user_awards")
