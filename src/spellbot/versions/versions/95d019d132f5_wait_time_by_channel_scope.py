"""Wait time by channel scope

Revision ID: 95d019d132f5
Revises: aae06e464fc4
Create Date: 2020-07-03 13:57:34.728319

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "95d019d132f5"
down_revision = "aae06e464fc4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wait_times") as b:
        b.add_column(sa.Column("channel_xid", sa.BigInteger()))


def downgrade():
    with op.batch_alter_table("wait_times") as b:
        b.drop_column("channel_xid")
