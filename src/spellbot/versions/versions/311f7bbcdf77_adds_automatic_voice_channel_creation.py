"""Adds automatic voice channel creation

Revision ID: 311f7bbcdf77
Revises: 055832354330
Create Date: 2020-10-08 13:23:46.013317

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "311f7bbcdf77"
down_revision = "055832354330"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("voice_channel_xid", sa.BigInteger(), nullable=True))

    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "create_voice", sa.Boolean(), server_default=sa.false(), nullable=False
            ),
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("create_voice")

    with op.batch_alter_table("games") as b:
        b.drop_column("voice_channel_xid")
