"""Use guild_xid for external guild id

Revision ID: 06c86186ed07
Revises: 36a0bdecd043
Create Date: 2020-07-02 13:00:34.468798

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "06c86186ed07"
down_revision = "36a0bdecd043"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("authorized_channels") as b:
        b.alter_column("guild", new_column_name="guild_xid")


def downgrade():
    with op.batch_alter_table("authorized_channels") as b:
        b.alter_column("guild_xid", new_column_name="guild")
