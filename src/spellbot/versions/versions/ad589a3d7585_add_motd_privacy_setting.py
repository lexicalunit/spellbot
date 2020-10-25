"""Add motd privacy setting

Revision ID: ad589a3d7585
Revises: ba58c2461a59
Create Date: 2020-10-24 20:41:03.351108

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ad589a3d7585"
down_revision = "ba58c2461a59"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "motd",
                sa.String(length=10),
                server_default=sa.text("'both'"),
                nullable=False,
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("motd")
