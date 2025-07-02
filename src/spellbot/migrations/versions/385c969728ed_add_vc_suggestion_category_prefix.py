"""
Add vc suggestion category prefix.

Revision ID: 385c969728ed
Revises: 389819d6480d
Create Date: 2025-07-02 10:29:01.569030
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "385c969728ed"
down_revision = "389819d6480d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "suggest_voice_category",
            sa.String(length=100),
            server_default=sa.text("NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "suggest_voice_category")
