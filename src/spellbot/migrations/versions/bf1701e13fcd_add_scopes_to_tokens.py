"""
Add scopes to tokens.

Revision ID: bf1701e13fcd
Revises: 0a69d68c3feb
Create Date: 2025-12-06 14:22:01.162693
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bf1701e13fcd"
down_revision = "0a69d68c3feb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tokens",
        sa.Column("scopes", sa.String(), server_default=sa.text("'*'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tokens", "scopes")
