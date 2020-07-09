"""Add game message column

Revision ID: 7e8e700f965c
Revises: 41e7b92c5577
Create Date: 2020-07-09 14:09:29.896651

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7e8e700f965c"
down_revision = "41e7b92c5577"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("message", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("message")
