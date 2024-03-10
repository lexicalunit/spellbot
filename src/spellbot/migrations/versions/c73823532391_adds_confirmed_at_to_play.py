"""
Adds confirmed_at to Play.

Revision ID: c73823532391
Revises: b2d4a9aa1aed
Create Date: 2024-03-09 10:17:45.037293

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c73823532391"
down_revision = "b2d4a9aa1aed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plays", sa.Column("confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("plays", "confirmed_at")
