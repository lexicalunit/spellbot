"""Refactor to replace queue logic with lfg

Revision ID: d5208ea8d47f
Revises: 6a1ea19d138f
Create Date: 2020-07-15 12:51:40.082517

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d5208ea8d47f"
down_revision = "6a1ea19d138f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("friendly")
        b.drop_column("scope")


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("scope", sa.VARCHAR(length=10), nullable=False))
        b.add_column(sa.Column("friendly", sa.BOOLEAN(), nullable=True))
