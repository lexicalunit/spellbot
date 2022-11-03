"""Move points config to channel

Revision ID: fd7ff2703f57
Revises: a1caf292fe93
Create Date: 2022-11-02 16:41:33.747604

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fd7ff2703f57"
down_revision = "a1caf292fe93"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "channels",
        sa.Column("show_points", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        """
        UPDATE channels
        SET show_points = g.show_points
        FROM guilds g
        WHERE channels.guild_xid = g.xid;
        """,
    )
    op.drop_column("guilds", "show_points")


def downgrade():
    op.add_column(
        "guilds",
        sa.Column(
            "show_points",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_column("channels", "show_points")
