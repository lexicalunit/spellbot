"""FK guild_xid

Revision ID: fff29f7559ac
Revises: 5ab9e1df9788
Create Date: 2020-07-04 10:26:00.028610

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fff29f7559ac"
down_revision = "5ab9e1df9788"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("authorized_channels") as b:
        b.create_foreign_key("fk_channels_guild", "servers", ["guild_xid"], ["guild_xid"])
    with op.batch_alter_table("games") as b:
        b.create_foreign_key("fk_games_guild", "servers", ["guild_xid"], ["guild_xid"])
    with op.batch_alter_table("servers") as b:
        b.add_column(
            sa.Column(
                "expire", sa.Integer(), nullable=False, server_default=sa.text("30")
            )
        )


def downgrade():
    with op.batch_alter_table("servers") as b:
        b.drop_column("expire")
    with op.batch_alter_table("games") as b:
        b.drop_constraint("fk_games_guild", type_="foreignkey")
    with op.batch_alter_table("authorized_channels") as b:
        b.drop_constraint("fk_channels_guild", type_="foreignkey")
