"""Adds created_at to reports

Revision ID: b887e657fb80
Revises: a86e8442192a
Create Date: 2020-08-16 17:59:04.926717

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b887e657fb80"
down_revision = "a86e8442192a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(op.f("ix_reports_game_id"), table_name="reports")
    op.drop_table("reports")

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("report", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_game_id"), "reports", ["game_id"], unique=False)


def downgrade():
    with op.batch_alter_table("reports") as b:
        b.drop_column("created_at")
