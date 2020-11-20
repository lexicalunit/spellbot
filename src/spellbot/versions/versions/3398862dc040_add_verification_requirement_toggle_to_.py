"""Add verification requirement toggle to channel settings

Revision ID: 3398862dc040
Revises: 1164f70e8dbe
Create Date: 2020-11-19 12:41:09.869576

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3398862dc040"
down_revision = "1164f70e8dbe"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(
            sa.Column(
                "require_verification",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )


def downgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("require_verification")
