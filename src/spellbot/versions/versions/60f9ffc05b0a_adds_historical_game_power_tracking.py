"""Adds historical game power tracking

Revision ID: 60f9ffc05b0a
Revises: 95106b5a352d
Create Date: 2020-08-22 08:17:13.008010

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "60f9ffc05b0a"
down_revision = "95106b5a352d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("game_power", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("game_power")
