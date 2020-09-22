"""Adds power command settings

Revision ID: 055832354330
Revises: a711319d9661
Create Date: 2020-09-22 15:12:17.097386

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "055832354330"
down_revision = "a711319d9661"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "power_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("power_enabled")
