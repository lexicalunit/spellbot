# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Resyncs the `tokens.id` sequence with the rows already in the table.

Tokens used to be inserted by hand with explicit ids, which doesn't advance the sequence,
so the first tokens created from the admin dashboard collided with existing ids. Moving the
sequence past the highest id fixes that. There's nothing to undo on downgrade.

Revision ID: 5d1e0c7a9b42
Revises: cbeb61d4a042
Create Date: 2026-11-03 18:45:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "5d1e0c7a9b42"
down_revision = "cbeb61d4a042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # With no rows, `is_called = false` makes the next id 1; otherwise it's MAX(id) + 1.
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('tokens', 'id'),
            COALESCE(MAX(id), 1),
            MAX(id) IS NOT NULL
        )
        FROM tokens
        """,
    )


def downgrade() -> None:
    pass
