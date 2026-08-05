"""
Adds web_actions table and guilds.web_games.

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-08-04 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c7d8e9f0a1b2"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column("web_games", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_table(
        "web_actions",
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
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("locale", sa.String(length=10), server_default=sa.text("'en'"), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "notices",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_web_actions_user_xid", "web_actions", ["user_xid"])
    op.create_index("ix_web_actions_guild_xid", "web_actions", ["guild_xid"])
    op.create_index("ix_web_actions_channel_xid", "web_actions", ["channel_xid"])
    op.create_index("ix_web_actions_game_id", "web_actions", ["game_id"])
    op.create_index("ix_web_actions_status_created_at", "web_actions", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_web_actions_status_created_at", table_name="web_actions")
    op.drop_index("ix_web_actions_game_id", table_name="web_actions")
    op.drop_index("ix_web_actions_channel_xid", table_name="web_actions")
    op.drop_index("ix_web_actions_guild_xid", table_name="web_actions")
    op.drop_index("ix_web_actions_user_xid", table_name="web_actions")
    op.drop_table("web_actions")
    op.drop_column("guilds", "web_games")
