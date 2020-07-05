"""Better expire logic

Revision ID: 8cb36f06a1af
Revises: dc915aa5af34
Create Date: 2020-07-05 11:19:39.239141

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8cb36f06a1af"
down_revision = "dc915aa5af34"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("updated_at")
        b.drop_column("expires_at")
