"""Support power levels

Revision ID: 5576ee9d4270
Revises: 95d019d132f5
Create Date: 2020-07-03 18:25:34.448242

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5576ee9d4270"
down_revision = "95d019d132f5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("power", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("power")
