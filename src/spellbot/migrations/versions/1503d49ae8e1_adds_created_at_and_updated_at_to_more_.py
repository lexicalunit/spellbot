"""
Adds created_at and updated_at to more models.

Revision ID: 1503d49ae8e1
Revises: c03099407b40
Create Date: 2023-10-04 13:40:31.315849

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1503d49ae8e1"
down_revision = "c03099407b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "blocks",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
    )
    op.add_column(
        "blocks",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
    )
    op.add_column(
        "plays",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
    )
    op.add_column(
        "plays",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("plays", "updated_at")
    op.drop_column("plays", "created_at")
    op.drop_column("blocks", "updated_at")
    op.drop_column("blocks", "created_at")
