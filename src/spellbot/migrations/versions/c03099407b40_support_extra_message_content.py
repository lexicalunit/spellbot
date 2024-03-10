"""
Support extra message content.

Revision ID: c03099407b40
Revises: 01766a5fb976
Create Date: 2023-09-04 19:39:19.981210

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c03099407b40"
down_revision = "01766a5fb976"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("extra", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("channels", "extra")
