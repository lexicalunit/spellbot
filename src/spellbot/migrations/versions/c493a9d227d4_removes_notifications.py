"""
Removes Notifications.

Revision ID: c493a9d227d4
Revises: a53eae0a3e4a
Create Date: 2026-02-12 17:08:19.296459
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c493a9d227d4"
down_revision = "a53eae0a3e4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_notifications_bracket"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_channel"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_format"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_guild"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_message"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_service"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_updated_at"), table_name="notifications")
    op.drop_table("notifications")


def downgrade() -> None:
    op.create_table(
        "notifications",
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
        sa.Column("started_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.Column("guild", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("channel", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column(
            "players",
            postgresql.ARRAY(sa.VARCHAR()),
            server_default=sa.text("'{}'::character varying[]"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "format",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "bracket",
            sa.INTEGER(),
            server_default=sa.text("1"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "service",
            sa.INTEGER(),
            server_default=sa.text("2"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("link", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("message", sa.BIGINT(), autoincrement=False, nullable=True),
        sa.Column("deleted_at", postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("notifications_pkey")),
    )
    op.create_index(
        op.f("ix_notifications_updated_at"),
        "notifications",
        ["updated_at"],
        unique=False,
    )
    op.create_index(op.f("ix_notifications_service"), "notifications", ["service"], unique=False)
    op.create_index(op.f("ix_notifications_message"), "notifications", ["message"], unique=False)
    op.create_index(op.f("ix_notifications_guild"), "notifications", ["guild"], unique=False)
    op.create_index(op.f("ix_notifications_format"), "notifications", ["format"], unique=False)
    op.create_index(op.f("ix_notifications_channel"), "notifications", ["channel"], unique=False)
    op.create_index(op.f("ix_notifications_bracket"), "notifications", ["bracket"], unique=False)
