"""
Adds game password support.

Revision ID: 0a7382dbcae6
Revises: 053fd7a31881
Create Date: 2024-11-30 16:31:51.016143
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0a7382dbcae6"
down_revision = "053fd7a31881"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("password", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("games", "password")
