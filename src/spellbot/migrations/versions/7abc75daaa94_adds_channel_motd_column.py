"""Adds channel motd column

Revision ID: 7abc75daaa94
Revises: c35c18ddd228
Create Date: 2021-11-09 14:37:10.136399

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7abc75daaa94"
down_revision = "c35c18ddd228"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("channels", sa.Column("motd", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("channels", "motd")
