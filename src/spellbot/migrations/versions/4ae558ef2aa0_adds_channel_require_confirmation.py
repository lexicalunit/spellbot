"""
Adds channel require_confirmation.

Revision ID: 4ae558ef2aa0
Revises: c73823532391
Create Date: 2024-03-10 12:10:08.955294

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ae558ef2aa0"
down_revision = "c73823532391"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "require_confirmation",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("channels", "require_confirmation")
