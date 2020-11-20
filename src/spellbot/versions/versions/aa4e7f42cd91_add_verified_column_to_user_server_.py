"""Add verified column to user server settings

Revision ID: aa4e7f42cd91
Revises: da6dc39b4882
Create Date: 2020-11-19 15:04:17.953982

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "aa4e7f42cd91"
down_revision = "da6dc39b4882"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_server_settings") as b:
        b.add_column(
            sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=True),
        )


def downgrade():
    with op.batch_alter_table("user_server_settings") as b:
        b.drop_column("verified")
