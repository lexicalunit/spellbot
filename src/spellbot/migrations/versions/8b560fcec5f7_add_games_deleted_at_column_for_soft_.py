"""Add games.deleted_at column for soft delete

Revision ID: 8b560fcec5f7
Revises: 6267f69c5dfd
Create Date: 2021-11-26 16:50:13.188559

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8b560fcec5f7"
down_revision = "6267f69c5dfd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("games", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_games_deleted_at"), "games", ["deleted_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_games_deleted_at"), table_name="games")
    op.drop_column("games", "deleted_at")
