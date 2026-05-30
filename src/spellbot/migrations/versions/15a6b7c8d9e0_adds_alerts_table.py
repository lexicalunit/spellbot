"""
Adds alerts table.

Revision ID: 15a6b7c8d9e0
Revises: 04b5c6d7e8f9
Create Date: 2026-05-30 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "15a6b7c8d9e0"
down_revision = "04b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_xid", "user_xid", name="uq_alerts_guild_user"),
    )
    op.create_index("ix_alerts_guild_xid", "alerts", ["guild_xid"])
    op.create_index("ix_alerts_user_xid", "alerts", ["user_xid"])


def downgrade() -> None:
    op.drop_index("ix_alerts_user_xid", table_name="alerts")
    op.drop_index("ix_alerts_guild_xid", table_name="alerts")
    op.drop_table("alerts")
