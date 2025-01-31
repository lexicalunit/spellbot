"""
Adds mythic track setting.

Revision ID: 432249d9ddbc
Revises: 2bf551e10a79
Create Date: 2025-01-30 20:38:52.336054
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "432249d9ddbc"
down_revision = "2bf551e10a79"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guilds",
        sa.Column(
            "enable_mythic_track",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_token_deleted_at"), "token", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_token_deleted_at"), table_name="token")
    op.drop_column("guilds", "enable_mythic_track")
