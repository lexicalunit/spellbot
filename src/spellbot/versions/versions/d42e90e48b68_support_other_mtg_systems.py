"""Support other MTG systems

Revision ID: d42e90e48b68
Revises: b8bf94efa410
Create Date: 2020-07-23 16:57:38.088983

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d42e90e48b68"
down_revision = "b8bf94efa410"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(
            sa.Column(
                "system",
                sa.String(length=30),
                server_default=sa.text("'spelltable'"),
                nullable=False,
            ),
        )


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("system")
