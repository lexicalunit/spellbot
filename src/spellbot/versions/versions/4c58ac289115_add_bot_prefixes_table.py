"""Add bot_prefixes table

Revision ID: 4c58ac289115
Revises: 06c86186ed07
Create Date: 2020-07-02 13:43:51.218180

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c58ac289115"
down_revision = "06c86186ed07"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bot_prefixes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("prefix", sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("bot_prefixes")
