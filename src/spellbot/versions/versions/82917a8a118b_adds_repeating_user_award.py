"""Adds repeating user award

Revision ID: 82917a8a118b
Revises: 87317566b389
Create Date: 2021-04-21 17:44:20.468956

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "82917a8a118b"
down_revision = "87317566b389"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("awards") as b:
        b.add_column(
            sa.Column(
                "repeating", sa.Boolean(), server_default=sa.false(), nullable=False
            ),
        )


def downgrade():
    with op.batch_alter_table("awards") as b:
        b.drop_column("repeating")
