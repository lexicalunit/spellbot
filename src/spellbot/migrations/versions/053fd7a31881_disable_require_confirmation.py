"""
Disable require_confirmation.

Revision ID: 053fd7a31881
Revises: 993303923867
Create Date: 2024-11-17 11:44:25.032571
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "053fd7a31881"
down_revision = "993303923867"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Disabling require confirmation settings for now until ELO system is reworked.
    op.execute("update games set requires_confirmation = false;")
    op.execute("update channels set require_confirmation = false;")


def downgrade() -> None:
    pass
