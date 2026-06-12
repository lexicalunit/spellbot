"""
Adds channel to_mode.

Revision ID: a8252b248858
Revises: 2dcac4a84d45
Create Date: 2026-06-11 20:59:50.448798

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a8252b248858"
down_revision = "2dcac4a84d45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "to_mode",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("channels", "to_mode")
