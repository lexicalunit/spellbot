"""Adds created_at for servers and users

Revision ID: 71ae365b621c
Revises: 9798bbb9c325
Create Date: 2020-10-14 10:50:20.748741

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "71ae365b621c"
down_revision = "9798bbb9c325"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # existing servers will have a created_at set to now
    with op.batch_alter_table("servers") as b:
        b.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
    conn.execute(sa.text("UPDATE servers SET created_at = :now"), now=datetime.utcnow())
    with op.batch_alter_table("servers") as b:
        b.alter_column("created_at", nullable=False)

    # existing users will have a created_at set to now
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
    conn.execute(sa.text("UPDATE users SET created_at = :now"), now=datetime.utcnow())
    with op.batch_alter_table("users") as b:
        b.alter_column("created_at", nullable=False)


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("created_at")

    with op.batch_alter_table("servers") as b:
        b.drop_column("created_at")
