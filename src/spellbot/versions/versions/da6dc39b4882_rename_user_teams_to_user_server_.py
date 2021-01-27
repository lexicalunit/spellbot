"""Rename user_teams to user_server_settings

Revision ID: da6dc39b4882
Revises: 3398862dc040
Create Date: 2020-11-19 14:44:55.671984

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "da6dc39b4882"
down_revision = "3398862dc040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_server_settings",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )
    conn = op.get_bind()
    conn.execute(
        """
        INSERT INTO user_server_settings (user_xid, guild_xid, team_id)
        SELECT user_xid, guild_xid, team_id
        FROM user_teams;
    """
    )
    op.drop_table("user_teams")


def downgrade():
    op.create_table(
        "user_teams",
        sa.Column("user_xid", sa.BIGINT(), nullable=False),
        sa.Column("guild_xid", sa.BIGINT(), nullable=False),
        sa.Column("team_id", sa.INTEGER(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["servers.guild_xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )
    conn = op.get_bind()
    conn.execute(
        """
        INSERT INTO user_teams (user_xid, guild_xid, team_id)
        SELECT user_xid, guild_xid, team_id
        FROM user_server_settings
        WHERE team_id IS NOT NULL;
    """
    )
    op.drop_table("user_server_settings")
