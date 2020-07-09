"""Add events table

Revision ID: db42410953c4
Revises: ee2447c63f27
Create Date: 2020-07-10 14:31:21.958947

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "db42410953c4"
down_revision = "ee2447c63f27"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("games") as b:
        b.add_column(sa.Column("event_id", sa.Integer(), nullable=True))
        b.create_foreign_key(
            "fk_events_games", "events", ["event_id"], ["id"], ondelete="SET NULL"
        )


def downgrade():
    with op.batch_alter_table("games") as b:
        b.drop_constraint("fk_events_games", type_="foreignkey")
        b.drop_column("event_id")
    op.drop_table("events")
