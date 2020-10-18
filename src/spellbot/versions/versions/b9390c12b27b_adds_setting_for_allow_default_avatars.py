"""Adds setting for allow_default_avatars

Revision ID: b9390c12b27b
Revises: b2e707d342be
Create Date: 2020-10-18 14:19:03.532665

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b9390c12b27b"
down_revision = "b2e707d342be"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "allow_default_avatars",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("allow_default_avatars")
