"""
Add playgroup_user_id to users.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-07 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("playgroup_user_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "playgroup_user_id")
