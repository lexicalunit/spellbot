# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Removes the user verification feature.

The verification columns and the `verify` table are kept so that their data isn't lost, but the
channel verification settings are no longer editable, so they're no longer audited either.

Revision ID: f8deb800833f
Revises: c5d6e7f8a9b0
Create Date: 2026-11-03 12:00:00.000000
"""

from alembic import op

from spellbot import audit

# revision identifiers, used by Alembic.
revision = "f8deb800833f"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    audit.attach_triggers(op.get_bind())


def downgrade() -> None:
    audit.attach_triggers(op.get_bind())
