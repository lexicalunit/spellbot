"""
Support multiple queues.

Revision ID: 01766a5fb976
Revises: fd7ff2703f57
Create Date: 2023-07-04 10:41:25.260104

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "01766a5fb976"
down_revision = "fd7ff2703f57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queues",
        sa.Column("user_xid", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_xid"], ["users.xid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_xid", "game_id"),
    )
    op.create_index(op.f("ix_queues_game_id"), "queues", ["game_id"], unique=False)
    op.drop_index("ix_users_game_id", table_name="users")
    op.drop_constraint("users_game_id_fkey", "users", type_="foreignkey")

    # inject all users' game_id into the new queue table
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT xid, game_id FROM users"))
    data = list(rows)
    for row in data:  # pragma: no cover
        user_xid = row[0]
        game_id = row[1]
        rows = conn.execute(
            sa.text("SELECT started_at, deleted_at FROM games WHERE id = :game_id"),
            {"game_id": game_id},
        )
        game_data = list(rows)
        # There _should_ only be one row, but just in case we'll default to False.
        # We only want to inject queue rows for games that have NOT started yet
        # and are NOT deleted.
        do_inject = (not game_data[0][0] and not game_data[0][1]) if game_data else False
        if do_inject:
            conn.execute(
                sa.text("INSERT INTO queues (user_xid, game_id) VALUES (:user_xid, :game_id)"),
                {
                    "user_xid": user_xid,
                    "game_id": game_id,
                },
            )

    op.drop_column("users", "game_id")


def downgrade() -> None:
    op.add_column("users", sa.Column("game_id", sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(
        "users_game_id_fkey",
        "users",
        "games",
        ["game_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_game_id", "users", ["game_id"], unique=False)

    # users' game_id will be the id from the last game they joined
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT user_xid, MAX(game_id) FROM queues GROUP BY user_xid;"))
    data = list(rows)
    for row in data:  # pragma: no cover
        conn.execute(
            sa.text("UPDATE users SET game_id = :game_id WHERE xid = :user_xid"),
            {
                "user_xid": row[0],
                "game_id": row[1],
            },
        )

    op.drop_index(op.f("ix_queues_game_id"), table_name="queues")
    op.drop_table("queues")
