"""Add games notes

Revision ID: 31d2fa4558a3
Revises: 253d7fc50dcc
Create Date: 2021-02-20 22:18:13.771616

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "31d2fa4558a3"
down_revision = "253d7fc50dcc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("note", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("note")
