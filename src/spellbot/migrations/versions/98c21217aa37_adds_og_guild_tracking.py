"""
Adds og guild tracking.

Revision ID: 98c21217aa37
Revises: 43faa588f3fc
Create Date: 2024-03-21 19:27:51.502557

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "98c21217aa37"
down_revision = "43faa588f3fc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plays", sa.Column("og_guild_xid", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE plays
        SET og_guild_xid = games.guild_xid
        FROM games
        WHERE games.id = plays.game_id
        """,
    )
    op.alter_column("plays", "og_guild_xid", nullable=False)

    op.add_column("queues", sa.Column("og_guild_xid", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE queues
        SET og_guild_xid = games.guild_xid
        FROM games
        WHERE games.id = queues.game_id
        """,
    )
    op.alter_column("queues", "og_guild_xid", nullable=False)


def downgrade() -> None:
    op.drop_column("queues", "og_guild_xid")
    op.drop_column("plays", "og_guild_xid")
