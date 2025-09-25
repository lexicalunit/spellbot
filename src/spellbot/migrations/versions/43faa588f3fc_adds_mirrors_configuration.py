"""
Adds mirrors configuration.

Revision ID: 43faa588f3fc
Revises: 96bc418971cd
Create Date: 2024-03-20 21:00:06.434522

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "43faa588f3fc"
down_revision = "96bc418971cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mirrors",
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
        sa.Column("from_guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("from_channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("to_guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("to_channel_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["from_channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint(
            "from_guild_xid",
            "from_channel_xid",
            "to_guild_xid",
            "to_channel_xid",
        ),
    )
    op.create_index(op.f("ix_posts_game_id"), "posts", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_posts_game_id"), table_name="posts")
    op.drop_table("mirrors")
