"""
Adds default_format to channel.

Revision ID: b2d4a9aa1aed
Revises: 1503d49ae8e1
Create Date: 2023-10-15 18:05:00.085956.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2d4a9aa1aed"
down_revision = "1503d49ae8e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "default_format",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_channels_default_format"),
        "channels",
        ["default_format"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_channels_default_format"), table_name="channels")
    op.drop_column("channels", "default_format")
