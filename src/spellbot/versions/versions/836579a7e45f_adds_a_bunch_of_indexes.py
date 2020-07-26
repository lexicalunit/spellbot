"""Adds a bunch of indexes

Revision ID: 836579a7e45f
Revises: d42e90e48b68
Create Date: 2020-07-25 17:46:12.616501

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "836579a7e45f"
down_revision = "d42e90e48b68"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "new_games_tags",
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("tag_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_id", "tag_id", name="game_tag_pk"),
    )
    op.get_bind().execute("INSERT INTO new_games_tags SELECT * FROM games_tags;")
    op.drop_table("games_tags")
    op.rename_table("new_games_tags", "games_tags")

    op.create_index(
        op.f("ix_channels_guild_xid"), "channels", ["guild_xid"], unique=False
    )
    op.create_index(op.f("ix_games_channel_xid"), "games", ["channel_xid"], unique=False)
    op.create_index(op.f("ix_games_event_id"), "games", ["event_id"], unique=False)
    op.create_index(op.f("ix_games_guild_xid"), "games", ["guild_xid"], unique=False)
    op.create_index(op.f("ix_games_size"), "games", ["size"], unique=False)
    op.create_index(op.f("ix_games_status"), "games", ["status"], unique=False)
    op.create_index(op.f("ix_games_system"), "games", ["system"], unique=False)
    op.create_index(op.f("ix_games_updated_at"), "games", ["updated_at"], unique=False)
    op.create_index(op.f("ix_users_game_id"), "users", ["game_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_users_game_id"), table_name="users")
    op.drop_index(op.f("ix_games_updated_at"), table_name="games")
    op.drop_index(op.f("ix_games_system"), table_name="games")
    op.drop_index(op.f("ix_games_status"), table_name="games")
    op.drop_index(op.f("ix_games_size"), table_name="games")
    op.drop_index(op.f("ix_games_guild_xid"), table_name="games")
    op.drop_index(op.f("ix_games_event_id"), table_name="games")
    op.drop_index(op.f("ix_games_channel_xid"), table_name="games")
    op.drop_index(op.f("ix_channels_guild_xid"), table_name="channels")

    op.create_table(
        "old_games_tags",
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("tag_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
    )
    op.get_bind().execute("INSERT INTO old_games_tags SELECT * FROM games_tags;")
    op.drop_table("games_tags")
    op.rename_table("old_games_tags", "games_tags")
