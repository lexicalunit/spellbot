"""Adds links setting

Revision ID: 7a2698d54c8a
Revises: 836579a7e45f
Create Date: 2020-08-12 18:56:32.420773

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7a2698d54c8a"
down_revision = "836579a7e45f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "links",
                sa.String(length=10),
                server_default=sa.text("'public'"),
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("links")
