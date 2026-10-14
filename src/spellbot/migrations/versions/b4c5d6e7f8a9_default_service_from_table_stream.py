# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Migrate default_service from Table Stream to Convoke.

Revision ID: b4c5d6e7f8a9
Revises: a7b8c9d0e1f2
Create Date: 2026-10-14 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE channels SET default_service = 9 WHERE default_service = 8;")


def downgrade() -> None:
    # Which channels used to default to Table Stream is not recoverable, and moving every
    # Convoke channel onto a dead service would be worse than leaving them alone.
    pass
