"""Adds historical plays

Revision ID: 7c101e86d86e
Revises: a7ad08c851d8
Create Date: 2021-03-29 19:41:16.046163

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7c101e86d86e"
down_revision = "a7ad08c851d8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plays",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "game_id"),
    )


def downgrade():
    op.drop_table("plays")
