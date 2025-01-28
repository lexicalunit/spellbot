"""
Adds play pins.

Revision ID: 2bf551e10a79
Revises: a59f2a831a84
Create Date: 2025-01-27 19:34:51.499841
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2bf551e10a79"
down_revision = "a59f2a831a84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plays", sa.Column("pin", sa.String(length=6), nullable=True))


def downgrade() -> None:
    op.drop_column("plays", "pin")
