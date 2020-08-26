"""Remove invitation columns

Revision ID: a711319d9661
Revises: 60f9ffc05b0a
Create Date: 2020-08-25 19:18:33.101446

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a711319d9661"
down_revision = "60f9ffc05b0a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("invite_confirmed")
        b.drop_column("invited")


def downgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(
            sa.Column(
                "invited", sa.BOOLEAN(), server_default=sa.text("(false)"), nullable=False
            ),
        )
        b.add_column(
            sa.Column(
                "invite_confirmed",
                sa.BOOLEAN(),
                server_default=sa.text("(false)"),
                nullable=False,
            ),
        )
