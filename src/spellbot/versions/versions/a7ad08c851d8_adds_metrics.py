"""Adds metrics

Revision ID: a7ad08c851d8
Revises: bbab2640b23b
Create Date: 2021-03-29 14:57:27.081092

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a7ad08c851d8"
down_revision = "bbab2640b23b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=True),
        sa.Column("guild_xid", sa.BigInteger(), nullable=True),
        sa.Column("channel_xid", sa.BigInteger(), nullable=True),
        sa.Column("user_xid", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_metrics_channel_xid"), "metrics", ["channel_xid"], unique=False
    )
    op.create_index(op.f("ix_metrics_guild_xid"), "metrics", ["guild_xid"], unique=False)
    op.create_index(op.f("ix_metrics_kind"), "metrics", ["kind"], unique=False)
    op.create_index(op.f("ix_metrics_user_xid"), "metrics", ["user_xid"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_metrics_user_xid"), table_name="metrics")
    op.drop_index(op.f("ix_metrics_kind"), table_name="metrics")
    op.drop_index(op.f("ix_metrics_guild_xid"), table_name="metrics")
    op.drop_index(op.f("ix_metrics_channel_xid"), table_name="metrics")
    op.drop_table("metrics")
