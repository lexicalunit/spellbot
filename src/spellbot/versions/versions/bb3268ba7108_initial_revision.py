"""Initial revision

Revision ID: bb3268ba7108
Revises:
Create Date: 2020-06-24 18:02:42.616375

"""
import sqlalchemy as sa
from alembic import op

revision = "bb3268ba7108"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "authorized_channels",
        sa.Column("guild", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("guild"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("users")
    op.drop_table("authorized_channels")
