"""Removing cruft since refactor

Revision ID: 0a01d60d4c38
Revises: d5208ea8d47f
Create Date: 2020-07-15 13:36:01.602982

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0a01d60d4c38"
down_revision = "d5208ea8d47f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("wait_times")
    with op.batch_alter_table("games") as b:
        b.drop_column("power")
    with op.batch_alter_table("users") as b:
        b.drop_column("queued_at")


def downgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("queued_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("power", sa.Float(), nullable=True))
    op.create_table(
        "wait_times",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
