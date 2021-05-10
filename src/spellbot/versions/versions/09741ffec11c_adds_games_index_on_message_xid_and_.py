"""Adds games index on message_xid and created_at

Revision ID: 09741ffec11c
Revises: 82917a8a118b
Create Date: 2021-05-10 13:01:02.650628

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "09741ffec11c"
down_revision = "82917a8a118b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f("ix_games_created_at"), "games", ["created_at"], unique=False)
    op.create_index(op.f("ix_games_message_xid"), "games", ["message_xid"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_games_message_xid"), table_name="games")
    op.drop_index(op.f("ix_games_created_at"), table_name="games")
