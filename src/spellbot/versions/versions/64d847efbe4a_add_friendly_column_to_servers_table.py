"""Add friendly column to servers table

Revision ID: 64d847efbe4a
Revises: db42410953c4
Create Date: 2020-07-11 16:11:04.621100

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "64d847efbe4a"
down_revision = "db42410953c4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("friendly", sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("friendly")
