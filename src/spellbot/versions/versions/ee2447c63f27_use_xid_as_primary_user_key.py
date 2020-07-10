"""Use xid as primary user key

Revision ID: ee2447c63f27
Revises: 7e8e700f965c
Create Date: 2020-07-09 16:48:13.534994

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ee2447c63f27"
down_revision = "7e8e700f965c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tmp",
        sa.Column("xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("xid"),
    )
    conn = op.get_bind()
    conn.execute(
        """
        INSERT INTO tmp (xid, game_id, queued_at)
        SELECT xid, game_id, queued_at
        FROM users;
    """
    )
    op.drop_table("users")
    op.rename_table("tmp", "users")


def downgrade():
    op.create_table(
        "tmp",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    conn = op.get_bind()
    conn.execute(
        """
        INSERT INTO tmp (xid, game_id, queued_at)
        SELECT xid, game_id, queued_at
        FROM users;
    """
    )
    op.drop_table("users")
    op.rename_table("tmp", "users")
