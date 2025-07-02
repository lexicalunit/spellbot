"""
Remove suggest_voice_channel column.

Revision ID: 3a2194f29016
Revises: 385c969728ed
Create Date: 2025-07-02 10:42:57.943061
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3a2194f29016"
down_revision = "385c969728ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("guilds", "suggest_voice_channel")


def downgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "suggest_voice_channel",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
