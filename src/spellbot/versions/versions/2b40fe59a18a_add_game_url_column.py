"""Add game url column

Revision ID: 2b40fe59a18a
Revises: 8cb36f06a1af
Create Date: 2020-07-05 18:04:49.643556

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2b40fe59a18a"
down_revision = "8cb36f06a1af"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("url", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("url")
