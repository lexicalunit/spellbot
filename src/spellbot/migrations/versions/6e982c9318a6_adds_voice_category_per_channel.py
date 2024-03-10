"""
Adds voice category per channel.

Revision ID: 6e982c9318a6
Revises: ef54f035a75c
Create Date: 2021-12-03 13:18:57.468342

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6e982c9318a6"
down_revision = "ef54f035a75c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "voice_category",
            sa.String(length=50),
            nullable=True,
            server_default=sa.text("'SpellBot Voice Channels'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("channels", "voice_category")
