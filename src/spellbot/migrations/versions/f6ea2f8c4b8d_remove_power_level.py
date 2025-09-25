"""
Remove power level.

Revision ID: f6ea2f8c4b8d
Revises: 4ae558ef2aa0
Create Date: 2024-03-10 14:32:38.735552

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6ea2f8c4b8d"
down_revision = "4ae558ef2aa0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("configs", "power_level")


def downgrade() -> None:
    op.add_column(
        "configs",
        sa.Column("power_level", sa.INTEGER(), autoincrement=False, nullable=True),
    )
