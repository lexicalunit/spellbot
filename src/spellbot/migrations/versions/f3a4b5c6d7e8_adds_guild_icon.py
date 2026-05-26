"""
Adds guild icon.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-05-26 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "icon",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "icon")
