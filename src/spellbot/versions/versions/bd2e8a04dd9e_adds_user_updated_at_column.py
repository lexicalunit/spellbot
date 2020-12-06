"""Adds user updated_at column

Revision ID: bd2e8a04dd9e
Revises: a1d4bbcc2831
Create Date: 2020-12-05 17:52:47.113798

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bd2e8a04dd9e"
down_revision = "a1d4bbcc2831"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # existing users will have an updated_at set its created_at
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
    conn.execute(sa.text("UPDATE users SET updated_at = created_at"))
    with op.batch_alter_table("users") as b:
        b.alter_column("updated_at", nullable=False)


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("updated_at")
