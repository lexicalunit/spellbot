"""Adds awards

Revision ID: 48be08d645a6
Revises: 7c101e86d86e
Create Date: 2021-04-20 19:38:19.222658

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "48be08d645a6"
down_revision = "7c101e86d86e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "awards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_xid", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("awards")
