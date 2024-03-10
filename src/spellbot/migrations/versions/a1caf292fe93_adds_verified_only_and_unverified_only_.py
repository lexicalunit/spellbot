"""
Adds verified_only and unverified_only to award table.

Revision ID: a1caf292fe93
Revises: c0bc12b1b482
Create Date: 2022-10-16 10:45:33.350102

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1caf292fe93"
down_revision = "c0bc12b1b482"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_awards",
        sa.Column("verified_only", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "guild_awards",
        sa.Column("unverified_only", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guild_awards", "unverified_only")
    op.drop_column("guild_awards", "verified_only")
