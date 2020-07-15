"""Track message external id for games

Revision ID: 6a1ea19d138f
Revises: 1013ebad5050
Create Date: 2020-07-14 14:58:48.950242

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6a1ea19d138f"
down_revision = "1013ebad5050"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("message_xid", sa.BigInteger(), nullable=True))


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("message_xid")
