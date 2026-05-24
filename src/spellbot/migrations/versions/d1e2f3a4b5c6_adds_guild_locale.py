"""
Adds guild locale.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-05-23 18:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "locale",
            sa.String(length=10),
            server_default=sa.text("'en'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "locale")
