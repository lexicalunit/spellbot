"""
Adds guild members.

Revision ID: a1b2c3d4e5f6
Revises: 0ab754dbe9d3
Create Date: 2026-04-02 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "0ab754dbe9d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_members",
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
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "guild_xid"),
    )
    op.create_index(
        op.f("ix_guild_members_guild_xid"),
        "guild_members",
        ["guild_xid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guild_members_user_xid"),
        "guild_members",
        ["user_xid"],
        unique=False,
    )

    # Populate guild_members from existing plays data
    # For each unique combination of user_xid and og_guild_xid in plays,
    # create a guild_member record
    op.execute(
        """
        INSERT INTO guild_members (user_xid, guild_xid, created_at, updated_at)
        SELECT DISTINCT
            p.user_xid,
            p.og_guild_xid,
            MIN(p.created_at),
            MAX(p.updated_at)
        FROM plays p
        INNER JOIN users u ON u.xid = p.user_xid
        INNER JOIN guilds g ON g.xid = p.og_guild_xid
        GROUP BY p.user_xid, p.og_guild_xid
        ON CONFLICT DO NOTHING
        """,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_guild_members_user_xid"), table_name="guild_members")
    op.drop_index(op.f("ix_guild_members_guild_xid"), table_name="guild_members")
    op.drop_table("guild_members")
