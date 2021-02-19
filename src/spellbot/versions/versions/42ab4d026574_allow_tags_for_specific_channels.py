"""Allow tags for specific channels

Revision ID: 42ab4d026574
Revises: d7a58c7aaeec
Create Date: 2021-02-19 10:34:07.039733

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "42ab4d026574"
down_revision = "d7a58c7aaeec"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(sa.Column("tags_enabled", sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("tags_enabled")
