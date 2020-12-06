"""Adds channel settings cached name column

Revision ID: 4ec681d6dbad
Revises: bd2e8a04dd9e
Create Date: 2020-12-06 12:44:47.162748

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4ec681d6dbad"
down_revision = "bd2e8a04dd9e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(sa.Column("cached_name", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("cached_name")
