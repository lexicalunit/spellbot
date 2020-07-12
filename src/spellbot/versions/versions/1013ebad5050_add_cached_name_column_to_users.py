"""Add cached name column to users

Revision ID: 1013ebad5050
Revises: 64d847efbe4a
Create Date: 2020-07-12 11:38:24.867699

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1013ebad5050"
down_revision = "64d847efbe4a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("cached_name", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("cached_name")
