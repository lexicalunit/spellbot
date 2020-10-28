"""Add cached server name

Revision ID: 6c1db37e135b
Revises: ad589a3d7585
Create Date: 2020-10-27 20:33:01.024610

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6c1db37e135b"
down_revision = "ad589a3d7585"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("cached_name", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("cached_name")
