"""Rebuild

Revision ID: dc915aa5af34
Revises:
Create Date: 2020-07-04 19:30:52.888268

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "dc915aa5af34"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "servers",
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("prefix", sa.String(length=10), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False),
        sa.Column("expire", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.PrimaryKeyConstraint("guild_xid"),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "wait_times",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "authorized_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=True),
        sa.Column("power", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "games_tags",
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("tag_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("users")
    op.drop_table("games_tags")
    op.drop_table("games")
    op.drop_table("authorized_channels")
    op.drop_table("wait_times")
    op.drop_table("tags")
    op.drop_table("servers")
