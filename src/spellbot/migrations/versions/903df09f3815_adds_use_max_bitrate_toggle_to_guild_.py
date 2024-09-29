"""
Adds use_max_bitrate toggle to guild model.

Revision ID: 903df09f3815
Revises: ffd25c8a3d06
Create Date: 2024-09-29 12:13:10.870525

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "903df09f3815"
down_revision = "ffd25c8a3d06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "use_max_bitrate",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("guilds", "use_max_bitrate")
