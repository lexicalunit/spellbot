"""UTC default created_at

Revision ID: 36a0bdecd043
Revises: 4ae86dc1a1c6
Create Date: 2020-07-02 12:16:55.784924

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "36a0bdecd043"
down_revision = "4ae86dc1a1c6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.alter_column(
            "created_at",
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
            server_default=None,
        )


def downgrade():
    with op.batch_alter_table("games") as b:
        b.alter_column(
            "created_at",
            existing_server_default=None,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )
