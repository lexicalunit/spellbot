"""Add game status column

Revision ID: 41e7b92c5577
Revises: b851801fb0cb
Create Date: 2020-07-08 15:47:01.048921

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "41e7b92c5577"
down_revision = "b851801fb0cb"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(
            sa.Column(
                "status",
                sa.String(length=30),
                server_default=sa.text("'pending'"),
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("status")
