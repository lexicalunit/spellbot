"""Adds server option for tags enabled

Revision ID: 9798bbb9c325
Revises: 8cb01e86be05
Create Date: 2020-10-14 08:58:51.745340

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9798bbb9c325"
down_revision = "8cb01e86be05"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "tags_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("tags_enabled")
