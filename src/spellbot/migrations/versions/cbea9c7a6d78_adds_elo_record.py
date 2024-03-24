"""
Adds elo record.

Revision ID: cbea9c7a6d78
Revises: 44f97f660362
Create Date: 2024-03-30 12:14:56.254209

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "cbea9c7a6d78"
down_revision = "44f97f660362"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "records",
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
        sa.Column("channel_xid", sa.BigInteger(), nullable=False),
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("elo", sa.Integer(), server_default="1500", nullable=False),
        sa.ForeignKeyConstraint(["channel_xid"], ["channels.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guild_xid"], ["guilds.xid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_xid", "channel_xid", "user_xid"),
    )


def downgrade() -> None:
    op.drop_table("records")
