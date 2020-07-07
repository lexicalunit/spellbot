"""Average power level

Revision ID: b851801fb0cb
Revises: 2b40fe59a18a
Create Date: 2020-07-06 17:20:57.658907

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b851801fb0cb"
down_revision = "2b40fe59a18a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.alter_column("power", existing_type=sa.Integer(), type_=sa.Float())


def downgrade():
    with op.batch_alter_table("games") as b:
        b.alter_column("power", existing_type=sa.Float(), type_=sa.Integer())
