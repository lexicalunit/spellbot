"""Add custom verification message

Revision ID: d29a8fff2485
Revises: 9172ecfb68e5
Create Date: 2020-11-22 19:46:50.601875

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d29a8fff2485"
down_revision = "9172ecfb68e5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(
            sa.Column("verify_message", sa.String(length=255), nullable=True),
        )


def downgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("verify_message")
