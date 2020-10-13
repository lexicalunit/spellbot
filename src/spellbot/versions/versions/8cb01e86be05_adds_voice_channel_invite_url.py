"""Adds voice channel invite url

Revision ID: 8cb01e86be05
Revises: e3ab9447b076
Create Date: 2020-10-13 09:49:54.983214

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8cb01e86be05"
down_revision = "e3ab9447b076"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(
            sa.Column("voice_channel_invite", sa.String(length=255), nullable=True),
        )


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_column("voice_channel_invite")
