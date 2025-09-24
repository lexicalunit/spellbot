"""
Delete score/elo/record cruft.

Revision ID: d97abaf70fcf
Revises: 2179aedacbff
Create Date: 2025-09-23 16:54:46.667622
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d97abaf70fcf"
down_revision = "2179aedacbff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("records")
    op.drop_column("channels", "show_points")
    op.drop_column("channels", "require_confirmation")
    op.drop_column("games", "requires_confirmation")
    op.drop_column("plays", "points")
    op.drop_column("plays", "confirmed_at")


def downgrade() -> None:
    op.add_column("plays", sa.Column("points", sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column(
        "games",
        sa.Column(
            "requires_confirmation",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "channels",
        sa.Column(
            "require_confirmation",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "plays",
        sa.Column("confirmed_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "channels",
        sa.Column(
            "show_points",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.create_table(
        "records",
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("(now() AT TIME ZONE 'utc'::text)"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("(now() AT TIME ZONE 'utc'::text)"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("guild_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("channel_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("user_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column(
            "elo",
            sa.INTEGER(),
            server_default=sa.text("1500"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["channel_xid"],
            ["channels.xid"],
            name=op.f("records_channel_xid_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guild_xid"],
            ["guilds.xid"],
            name=op.f("records_guild_xid_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_xid"],
            ["users.xid"],
            name=op.f("records_user_xid_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("guild_xid", "channel_xid", "user_xid", name=op.f("records_pkey")),
    )
