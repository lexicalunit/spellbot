"""Adds created_at and updated_at for channel_settings

Revision ID: 907102748ac5
Revises: 4ec681d6dbad
Create Date: 2020-12-06 12:53:43.458526

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "907102748ac5"
down_revision = "4ec681d6dbad"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # existing channel_settings will have an created_at set to now
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
    conn.execute(
        sa.text("UPDATE channel_settings SET created_at = :now"), now=datetime.utcnow()
    )
    with op.batch_alter_table("channel_settings") as b:
        b.alter_column("created_at", nullable=False)

    # existing channel_settings will have an updated_at set to now
    with op.batch_alter_table("channel_settings") as b:
        b.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
    conn.execute(
        sa.text("UPDATE channel_settings SET updated_at = :now"), now=datetime.utcnow()
    )
    with op.batch_alter_table("channel_settings") as b:
        b.alter_column("updated_at", nullable=False)


def downgrade():
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("updated_at")
    with op.batch_alter_table("channel_settings") as b:
        b.drop_column("created_at")
