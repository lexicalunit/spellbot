"""Add server motd setting

Revision ID: ba58c2461a59
Revises: b9390c12b27b
Create Date: 2020-10-24 11:21:37.677827

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ba58c2461a59"
down_revision = "b9390c12b27b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("smotd", sa.String(length=255), nullable=True))
        b.drop_column("allow_default_avatars")


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "allow_default_avatars",
                sa.BOOLEAN(),
                server_default=sa.true(),
                nullable=False,
            ),
        )
        b.drop_column("smotd")
