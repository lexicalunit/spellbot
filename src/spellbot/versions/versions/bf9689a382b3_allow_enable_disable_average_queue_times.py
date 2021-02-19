"""Allow enable/disable average queue times

Revision ID: bf9689a382b3
Revises: 42ab4d026574
Create Date: 2021-02-19 12:41:02.393856

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bf9689a382b3"
down_revision = "42ab4d026574"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(sa.Column("queue_time_enabled", sa.Boolean(), nullable=True))
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "queue_time_enabled",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("queue_time_enabled")
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("queue_time_enabled")
