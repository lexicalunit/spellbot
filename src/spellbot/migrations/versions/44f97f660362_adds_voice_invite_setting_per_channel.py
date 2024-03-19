"""
Adds voice invite setting per channel.

Revision ID: 44f97f660362
Revises: 98c21217aa37
Create Date: 2024-03-22 20:43:02.937294

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "44f97f660362"
down_revision = "98c21217aa37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("voice_invite", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("channels", "voice_invite")
