"""
Add note to tokens table.

Revision ID: 0a69d68c3feb
Revises: 72d381e804b4
Create Date: 2025-12-06 13:25:35.679723
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0a69d68c3feb"
down_revision = "72d381e804b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tokens",
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
        sa.Column("note", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tokens_deleted_at"), "tokens", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_tokens_key"), "tokens", ["key"], unique=False)
    op.execute(
        """
        INSERT INTO tokens (id, created_at, updated_at, deleted_at, key)
        SELECT id, created_at, updated_at, deleted_at, key
        FROM token
        """,
    )
    op.drop_index(op.f("ix_token_deleted_at"), table_name="token")
    op.drop_index(op.f("ix_token_key"), table_name="token")
    op.drop_table("token")


def downgrade() -> None:
    op.create_table(
        "token",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("(now() AT TIME ZONE 'utc'::text)"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("(now() AT TIME ZONE 'utc'::text)"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("deleted_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.Column("key", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("token_pkey")),
    )
    op.create_index(op.f("ix_token_key"), "token", ["key"], unique=False)
    op.create_index(op.f("ix_token_deleted_at"), "token", ["deleted_at"], unique=False)
    op.drop_index(op.f("ix_tokens_key"), table_name="tokens")
    op.drop_index(op.f("ix_tokens_deleted_at"), table_name="tokens")
    op.drop_table("tokens")
