"""Removes voice invite link

Revision ID: a3d6ab2c2e6b
Revises: fd7ff2703f57
Create Date: 2023-04-25 11:11:36.896307

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a3d6ab2c2e6b"
down_revision = "fd7ff2703f57"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("games", "voice_invite_link")


def downgrade():
    op.add_column(
        "games",
        sa.Column("voice_invite_link", sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    )
