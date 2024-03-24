"""
Adds requires_confirmation column to games.

Revision ID: aa9db9f03293
Revises: cbea9c7a6d78
Create Date: 2024-03-30 12:54:28.963868

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "aa9db9f03293"
down_revision = "cbea9c7a6d78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column(
            "requires_confirmation",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("games", "requires_confirmation")
