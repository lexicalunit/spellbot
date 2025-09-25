"""
Remove user configs.

Revision ID: ea8f33717a54
Revises: f6ea2f8c4b8d
Create Date: 2024-03-10 23:34:24.880337

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ea8f33717a54"
down_revision = "f6ea2f8c4b8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("configs")


def downgrade() -> None:
    op.create_table(
        "configs",
        sa.Column("guild_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("user_xid", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["guild_xid"],
            ["guilds.xid"],
            name="configs_guild_xid_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_xid"],
            ["users.xid"],
            name="configs_user_xid_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("guild_xid", "user_xid", name="configs_pkey"),
    )
