"""Adds ability to ban users

Revision ID: 83c728a2823e
Revises: 724f0be37f9a
Create Date: 2021-02-25 17:07:46.195390

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "83c728a2823e"
down_revision = "724f0be37f9a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(
            sa.Column("banned", sa.Boolean(), server_default=sa.false(), nullable=False),
        )


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("banned")
