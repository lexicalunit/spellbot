"""Adds voice channels category

Revision ID: e3ab9447b076
Revises: 311f7bbcdf77
Create Date: 2020-10-12 16:06:46.843494

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e3ab9447b076"
down_revision = "311f7bbcdf77"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("voice_category_xid", sa.BigInteger(), nullable=True))


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("voice_category_xid")
