"""Adds game reports

Revision ID: a86e8442192a
Revises: ba6af6c62640
Create Date: 2020-08-16 14:33:36.157320

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a86e8442192a"
down_revision = "ba6af6c62640"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("report", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_game_id"), "reports", ["game_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_reports_game_id"), table_name="reports")
    op.drop_table("reports")
