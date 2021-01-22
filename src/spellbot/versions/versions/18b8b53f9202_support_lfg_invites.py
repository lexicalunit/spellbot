"""Support lfg invites

Revision ID: 18b8b53f9202
Revises: 0a01d60d4c38
Create Date: 2020-07-17 11:10:19.106275

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "18b8b53f9202"
down_revision = "0a01d60d4c38"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as b:
        b.add_column(
            sa.Column(
                "invite_confirmed",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )
        b.add_column(
            sa.Column("invited", sa.Boolean(), server_default=sa.false(), nullable=False),
        )


def downgrade():
    with op.batch_alter_table("users") as b:
        b.drop_column("invited")
        b.drop_column("invite_confirmed")
