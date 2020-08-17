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
    with op.batch_alter_table("reports") as b:
        b.add_column(
            sa.Column(
                "created_at", sa.DateTime(), nullable=False, default=datetime.utcnow
            )
        )


def downgrade():
    with op.batch_alter_table("reports") as b:
        b.drop_column("created_at")
