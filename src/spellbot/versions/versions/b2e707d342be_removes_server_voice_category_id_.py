"""Removes server voice category id tracking

Revision ID: b2e707d342be
Revises: 71ae365b621c
Create Date: 2020-10-16 21:36:47.067762

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2e707d342be"
down_revision = "71ae365b621c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("voice_category_xid")


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("voice_category_xid", sa.BIGINT(), nullable=True))
