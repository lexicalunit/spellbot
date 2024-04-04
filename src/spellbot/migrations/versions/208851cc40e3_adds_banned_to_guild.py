"""
Adds banned to guild.

Revision ID: 208851cc40e3
Revises: aa9db9f03293
Create Date: 2024-04-04 08:52:39.309747

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "208851cc40e3"
down_revision = "aa9db9f03293"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column("banned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guilds", "banned")
