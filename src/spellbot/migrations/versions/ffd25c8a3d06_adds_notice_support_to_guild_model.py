"""
Adds notice support to guild model.

Revision ID: ffd25c8a3d06
Revises: 208851cc40e3
Create Date: 2024-06-08 18:52:40.575385

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ffd25c8a3d06"
down_revision = "208851cc40e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "notice",
            sa.String(length=255),
            server_default=sa.text("NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "notice")
