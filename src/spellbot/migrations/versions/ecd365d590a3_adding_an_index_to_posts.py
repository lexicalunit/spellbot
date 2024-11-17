"""
Adding an index to posts.

Revision ID: ecd365d590a3
Revises: 903df09f3815
Create Date: 2024-11-17 10:28:01.584925
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "ecd365d590a3"
down_revision = "903df09f3815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_posts_message_xid"), "posts", ["message_xid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_posts_message_xid"), table_name="posts")
