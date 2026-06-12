"""
Install settings audit (postgresql-audit) on channels and guilds.

Creates the `audit` schema (postgresql-audit `transaction`/`activity` tables, JSONB
operators/functions) and attaches statement-level triggers that record every settings change into
`audit.activity`. Which columns are audited is defined in `spellbot.audit` (see `audited_columns`),
not here; this migration just calls the installer.

Revision ID: 9ac713becc5a
Revises: a8252b248858
Create Date: 2026-06-11 21:40:39.035790

"""

from alembic import op

from spellbot import audit

# revision identifiers, used by Alembic.
revision = "9ac713becc5a"
down_revision = "a8252b248858"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    audit.install(bind)
    audit.attach_triggers(bind)


def downgrade() -> None:
    audit.uninstall(op.get_bind())
