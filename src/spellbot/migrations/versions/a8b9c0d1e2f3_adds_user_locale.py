"""
Adds user locale.

Revision ID: a8b9c0d1e2f3
Revises: 17dbc920d074
Create Date: 2026-05-20 10:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a8b9c0d1e2f3"
down_revision = "17dbc920d074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.String(length=10),
            server_default=sa.text("'en'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "locale")
