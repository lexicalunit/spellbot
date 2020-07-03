"""Adds wait time tracking

Revision ID: 2ad0a1c189cc
Revises: 4c58ac289115
Create Date: 2020-07-03 11:29:58.560742

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2ad0a1c189cc"
down_revision = "4c58ac289115"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wait_times",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("queued_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("queued_at")
    op.drop_table("wait_times")
