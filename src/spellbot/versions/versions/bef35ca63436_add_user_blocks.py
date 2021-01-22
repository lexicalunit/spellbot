"""Add user blocks

Revision ID: bef35ca63436
Revises: 84903dda8911
Create Date: 2021-01-22 14:41:08.839592

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bef35ca63436"
down_revision = "84903dda8911"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users_blocks",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("blocked_user_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["blocked_user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "blocked_user_xid"),
        sa.UniqueConstraint("user_xid", "blocked_user_xid", name="uix_1"),
    )
    op.create_index(
        op.f("ix_users_blocks_blocked_user_xid"),
        "users_blocks",
        ["blocked_user_xid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_users_blocks_user_xid"), "users_blocks", ["user_xid"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_users_blocks_user_xid"), table_name="users_blocks")
    op.drop_index(op.f("ix_users_blocks_blocked_user_xid"), table_name="users_blocks")
    op.drop_table("users_blocks")
