"""
Adds voice channel suggestions.

Revision ID: 6f5fb731f4c1
Revises: 0a7382dbcae6
Create Date: 2025-01-01 11:43:54.940328

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6f5fb731f4c1"
down_revision = "0a7382dbcae6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "suggest_voice_channel",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "suggest_voice_channel")
