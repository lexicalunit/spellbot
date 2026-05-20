"""
Adds game locale.

Revision ID: 17dbc920d074
Revises: c4d5e6f7a8b9
Create Date: 2026-05-19 17:58:40.070249
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "17dbc920d074"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column(
            "locale",
            sa.String(length=255),
            server_default=sa.text("'en'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("games", "locale")
