"""
Adds api tokens.

Revision ID: a59f2a831a84
Revises: 6f5fb731f4c1
Create Date: 2025-01-27 19:23:45.776047
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a59f2a831a84"
down_revision = "6f5fb731f4c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "token",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_key"), "token", ["key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_token_key"), table_name="token")
    op.drop_table("token")
