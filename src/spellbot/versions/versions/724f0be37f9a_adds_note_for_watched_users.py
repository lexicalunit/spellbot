"""Adds note for watched users

Revision ID: 724f0be37f9a
Revises: 31d2fa4558a3
Create Date: 2021-02-22 20:37:33.483055

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "724f0be37f9a"
down_revision = "31d2fa4558a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("watched_users") as b:
        b.add_column(sa.Column("note", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("watched_users") as b:
        b.drop_column("note")
