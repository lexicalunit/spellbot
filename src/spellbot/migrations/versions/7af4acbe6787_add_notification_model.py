"""
Add notification model.

Revision ID: 7af4acbe6787
Revises: d97abaf70fcf
Create Date: 2025-12-05 18:32:27.653358
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7af4acbe6787"
down_revision = "d97abaf70fcf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
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
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("guild", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.BigInteger(), nullable=False),
        sa.Column("players", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("format", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("bracket", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("service", sa.Integer(), server_default=sa.text("2"), nullable=False),
        sa.Column("link", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_bracket"), "notifications", ["bracket"], unique=False)
    op.create_index(op.f("ix_notifications_channel"), "notifications", ["channel"], unique=False)
    op.create_index(op.f("ix_notifications_format"), "notifications", ["format"], unique=False)
    op.create_index(op.f("ix_notifications_guild"), "notifications", ["guild"], unique=False)
    op.create_index(op.f("ix_notifications_service"), "notifications", ["service"], unique=False)
    op.create_index(
        op.f("ix_notifications_updated_at"),
        "notifications",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_updated_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_service"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_guild"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_format"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_channel"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_bracket"), table_name="notifications")
    op.drop_table("notifications")
