"""Queues

Revision ID: 6f160f1bf688
Revises: bb3268ba7108
Create Date: 2020-06-24 20:14:32.753166

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6f160f1bf688"
down_revision = "bb3268ba7108"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("guild", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("queue") as b:
        b.create_foreign_key(
            "fk_queue_user", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade():
    with op.batch_alter_table("queue") as b:
        b.drop_constraint("fk_queue_user", type_="foreignkey")

    op.drop_table("queue")
