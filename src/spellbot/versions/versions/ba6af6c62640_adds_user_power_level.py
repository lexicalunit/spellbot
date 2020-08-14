"""Adds user power level

Revision ID: ba6af6c62640
Revises: 7a2698d54c8a
Create Date: 2020-08-14 14:49:21.107946

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ba6af6c62640"
down_revision = "7a2698d54c8a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("power", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("power")
