"""Remove legacy prefix

Revision ID: 6267f69c5dfd
Revises: ee653a3075c6
Create Date: 2021-11-25 20:23:35.556348

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6267f69c5dfd"
down_revision = "ee653a3075c6"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("guilds", "legacy_prefix")


def downgrade():
    op.add_column(
        "guilds",
        sa.Column(
            "legacy_prefix",
            sa.VARCHAR(length=10),
            server_default=sa.text("'!'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
    )
