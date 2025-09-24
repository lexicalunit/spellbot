"""
Track game posts.

Revision ID: 96bc418971cd
Revises: 778ca30416dd
Create Date: 2024-03-20 15:53:07.808999

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "96bc418971cd"
down_revision = "778ca30416dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "posts",
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
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("message_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_xid", "channel_xid", "message_xid"),
    )
    op.execute(
        """
            INSERT INTO posts (game_id, guild_xid, channel_xid, message_xid)
            SELECT id, guild_xid, channel_xid, message_xid
            FROM games
            WHERE message_xid IS NOT NULL
        """,
    )
    op.drop_index("ix_games_message_xid", table_name="games")
    op.drop_column("games", "message_xid")


def downgrade() -> None:
    op.add_column(
        "games",
        sa.Column("message_xid", sa.BIGINT(), autoincrement=False, nullable=True),
    )
    op.create_index("ix_games_message_xid", "games", ["message_xid"], unique=False)
    op.execute(
        """
            UPDATE games
            SET message_xid = posts.message_xid
            FROM posts
            WHERE posts.game_id = games.id
                AND posts.guild_xid = games.guild_xid
                AND posts.channel_xid = games.channel_xid
        """,
    )
    op.drop_table("posts")
