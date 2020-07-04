"""Channel bookkeeping for games

Revision ID: 5ab9e1df9788
Revises: 5576ee9d4270
Create Date: 2020-07-03 22:04:40.143396

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5ab9e1df9788"
down_revision = "5576ee9d4270"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("channel_xid", sa.BigInteger(), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("channel_xid")
