"""Add custom voice category

Revision ID: d7a58c7aaeec
Revises: bef35ca63436
Create Date: 2021-01-28 11:31:02.043758

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d7a58c7aaeec"
down_revision = "bef35ca63436"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column("voice_category_prefix", sa.String(length=40), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("voice_category_prefix")
