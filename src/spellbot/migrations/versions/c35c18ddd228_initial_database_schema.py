"""initial database schema

Revision ID: c35c18ddd228
Revises:
Create Date: 2021-10-22 01:48:21.117002

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c35c18ddd228"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guilds",
        sa.Column("xid", sa.BigInteger(), nullable=False),
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
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("motd", sa.String(length=255), nullable=True),
        sa.Column(
            "show_links",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "voice_create",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "show_points",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "legacy_prefix",
            sa.String(length=10),
            server_default=sa.text("'!'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("xid"),
    )
    op.create_table(
        "verify",
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column(
            "verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("guild_xid", "user_xid"),
    )
    op.create_table(
        "channels",
        sa.Column("xid", sa.BigInteger(), nullable=False),
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
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column(
            "default_seats",
            sa.Integer(),
            server_default=sa.text("4"),
            nullable=False,
        ),
        sa.Column(
            "auto_verify",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "unverified_only",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "verified_only",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("xid"),
    )
    op.create_index(
        op.f("ix_channels_guild_xid"),
        "channels",
        ["guild_xid"],
        unique=False,
    )
    op.create_table(
        "guild_awards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column(
            "repeating",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_guild_awards_count"),
        "guild_awards",
        ["count"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guild_awards_guild_xid"),
        "guild_awards",
        ["guild_xid"],
        unique=False,
    )
    op.create_table(
        "games",
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
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("message_xid", sa.BigInteger(), nullable=True),
        sa.Column("voice_xid", sa.BigInteger(), nullable=True),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("status", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("format", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("spelltable_link", sa.String(length=255), nullable=True),
        sa.Column("voice_invite_link", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_games_channel_xid"), "games", ["channel_xid"], unique=False)
    op.create_index(op.f("ix_games_format"), "games", ["format"], unique=False)
    op.create_index(op.f("ix_games_guild_xid"), "games", ["guild_xid"], unique=False)
    op.create_index(op.f("ix_games_message_xid"), "games", ["message_xid"], unique=False)
    op.create_index(op.f("ix_games_seats"), "games", ["seats"], unique=False)
    op.create_index(op.f("ix_games_status"), "games", ["status"], unique=False)
    op.create_index(op.f("ix_games_voice_xid"), "games", ["voice_xid"], unique=False)
    op.create_table(
        "users",
        sa.Column("xid", sa.BigInteger(), nullable=False),
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
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "banned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("xid"),
    )
    op.create_index(op.f("ix_users_game_id"), "users", ["game_id"], unique=False)
    op.create_table(
        "blocks",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("blocked_user_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["blocked_user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "blocked_user_xid"),
    )
    op.create_index(
        op.f("ix_blocks_blocked_user_xid"),
        "blocks",
        ["blocked_user_xid"],
        unique=False,
    )
    op.create_index(op.f("ix_blocks_user_xid"), "blocks", ["user_xid"], unique=False)
    op.create_table(
        "plays",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "game_id"),
    )
    op.create_table(
        "user_awards",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_award_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )
    op.create_index(
        op.f("ix_user_awards_guild_xid"),
        "user_awards",
        ["guild_xid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_awards_user_xid"),
        "user_awards",
        ["user_xid"],
        unique=False,
    )
    op.create_table(
        "watches",
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_xid", "user_xid"),
    )


def downgrade():
    op.drop_table("watches")
    op.drop_index(op.f("ix_user_awards_user_xid"), table_name="user_awards")
    op.drop_index(op.f("ix_user_awards_guild_xid"), table_name="user_awards")
    op.drop_table("user_awards")
    op.drop_table("plays")
    op.drop_index(op.f("ix_blocks_user_xid"), table_name="blocks")
    op.drop_index(op.f("ix_blocks_blocked_user_xid"), table_name="blocks")
    op.drop_table("blocks")
    op.drop_index(op.f("ix_users_game_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_games_voice_xid"), table_name="games")
    op.drop_index(op.f("ix_games_status"), table_name="games")
    op.drop_index(op.f("ix_games_seats"), table_name="games")
    op.drop_index(op.f("ix_games_message_xid"), table_name="games")
    op.drop_index(op.f("ix_games_guild_xid"), table_name="games")
    op.drop_index(op.f("ix_games_format"), table_name="games")
    op.drop_index(op.f("ix_games_channel_xid"), table_name="games")
    op.drop_table("games")
    op.drop_index(op.f("ix_guild_awards_guild_xid"), table_name="guild_awards")
    op.drop_index(op.f("ix_guild_awards_count"), table_name="guild_awards")
    op.drop_table("guild_awards")
    op.drop_index(op.f("ix_channels_guild_xid"), table_name="channels")
    op.drop_table("channels")
    op.drop_table("verify")
    op.drop_table("guilds")
