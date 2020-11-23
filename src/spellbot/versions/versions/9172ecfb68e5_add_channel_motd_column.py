"""Add channel motd column

Revision ID: 9172ecfb68e5
Revises: aa4e7f42cd91
Create Date: 2020-11-22 17:53:28.138208

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9172ecfb68e5"
down_revision = "aa4e7f42cd91"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(sa.Column("cmotd", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("cmotd")
