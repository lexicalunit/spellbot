"""Adds delete_expired column to channel

Revision ID: c0bc12b1b482
Revises: 42f55401ef2b
Create Date: 2022-10-15 10:52:55.916210

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c0bc12b1b482"
down_revision = "42f55401ef2b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "channels",
        sa.Column(
            "delete_expired",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("channels", "delete_expired")
