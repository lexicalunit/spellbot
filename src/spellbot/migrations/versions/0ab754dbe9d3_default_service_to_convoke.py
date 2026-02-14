"""
Migrate default_service from SpellTable to Convoke.

Revision ID: 0ab754dbe9d3
Revises: c493a9d227d4
Create Date: 2026-02-14 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0ab754dbe9d3"
down_revision = "c493a9d227d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE channels SET default_service = 9 WHERE default_service = 2;")


def downgrade() -> None:
    op.execute("UPDATE channels SET default_service = 2 WHERE default_service = 9;")
