"""Adds tourney support

Revision ID: 6f34353a3af3
Revises: 42f55401ef2b
Create Date: 2022-09-20 14:07:28.398840

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6f34353a3af3"
down_revision = "42f55401ef2b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tourneys",
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
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("message_xid", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("format", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("name", sa.String(length=100), server_default="", nullable=False),
        sa.Column("description", sa.String(length=100), server_default="", nullable=False),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tourneys_channel_xid"), "tourneys", ["channel_xid"], unique=False)
    op.create_index(op.f("ix_tourneys_deleted_at"), "tourneys", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_tourneys_format"), "tourneys", ["format"], unique=False)
    op.create_index(op.f("ix_tourneys_guild_xid"), "tourneys", ["guild_xid"], unique=False)
    op.create_index(op.f("ix_tourneys_message_xid"), "tourneys", ["message_xid"], unique=False)
    op.create_index(op.f("ix_tourneys_status"), "tourneys", ["status"], unique=False)
    op.add_column("games", sa.Column("tourney_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_games_tourney_id"), "games", ["tourney_id"], unique=False)
    op.create_foreign_key(
        "games_tourney_id_fkey",
        "games",
        "tourneys",
        ["tourney_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("users", sa.Column("tourney_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_tourney_id"), "users", ["tourney_id"], unique=False)
    op.create_foreign_key(
        "users_tourney_id_fkey",
        "users",
        "tourneys",
        ["tourney_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("users_tourney_id_fkey", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_tourney_id"), table_name="users")
    op.drop_column("users", "tourney_id")
    op.drop_constraint("games_tourney_id_fkey", "games", type_="foreignkey")
    op.drop_index(op.f("ix_games_tourney_id"), table_name="games")
    op.drop_column("games", "tourney_id")
    op.drop_index(op.f("ix_tourneys_status"), table_name="tourneys")
    op.drop_index(op.f("ix_tourneys_message_xid"), table_name="tourneys")
    op.drop_index(op.f("ix_tourneys_guild_xid"), table_name="tourneys")
    op.drop_index(op.f("ix_tourneys_format"), table_name="tourneys")
    op.drop_index(op.f("ix_tourneys_deleted_at"), table_name="tourneys")
    op.drop_index(op.f("ix_tourneys_channel_xid"), table_name="tourneys")
    op.drop_table("tourneys")
