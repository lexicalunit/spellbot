"""
Adds pin verification.

Revision ID: 389819d6480d
Revises: d1fca945a660
Create Date: 2025-02-15 13:11:56.803245
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "389819d6480d"
down_revision = "d1fca945a660"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plays", sa.Column("verified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("plays", "verified_at")
