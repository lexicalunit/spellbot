"""Adds server spectator link settings

Revision ID: a1d4bbcc2831
Revises: d29a8fff2485
Create Date: 2020-12-04 16:22:18.842717

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1d4bbcc2831"
down_revision = "d29a8fff2485"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "show_spectate_link",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("show_spectate_link")
