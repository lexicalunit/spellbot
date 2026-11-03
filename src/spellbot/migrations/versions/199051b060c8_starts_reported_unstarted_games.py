# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Starts games that were reported as played but never started.

A Guild War game opens its Convoke table before it fills, so it could be played on Convoke
and reported back without ever starting in SpellBot, which then expired it. SpellBot now
starts such a game when its report arrives; this applies the same to the games reported
before that. Each one is marked started at the time its report gives (or when it was last
updated, if the report has none) and is no longer deleted. Every reported player with a
Discord ID that SpellBot knows gets a play.

Revision ID: 199051b060c8
Revises: 1553b5dd225d
Create Date: 2026-11-03 14:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "199051b060c8"
down_revision = "1553b5dd225d"
branch_labels = None
depends_on = None

# Report fields come from Convoke, so they're only cast once `pg_input_is_valid` accepts them.
STATEMENTS = (
    """
    CREATE TEMPORARY TABLE reported_unstarted ON COMMIT DROP AS
    SELECT id, guild_xid, metadata
    FROM games
    WHERE started_at IS NULL AND jsonb_typeof(metadata->'players') = 'array'
    """,
    """
    INSERT INTO plays (user_xid, game_id, og_guild_xid)
    SELECT DISTINCT u.xid, g.id, g.guild_xid
    FROM reported_unstarted g
    CROSS JOIN LATERAL jsonb_array_elements(g.metadata->'players') player
    JOIN users u ON u.xid = CASE
        WHEN jsonb_typeof(player) = 'object' AND pg_input_is_valid(player->>'xid', 'bigint')
        THEN (player->>'xid')::bigint
    END
    ON CONFLICT DO NOTHING
    """,
    "DELETE FROM queues WHERE game_id IN (SELECT id FROM reported_unstarted)",
    """
    UPDATE games
    SET
        status = 2, -- `GameStatus.STARTED`
        deleted_at = NULL,
        started_at = CASE
            WHEN pg_input_is_valid(metadata->>'started_at', 'timestamptz')
            THEN (metadata->>'started_at')::timestamptz AT TIME ZONE 'UTC'
            ELSE updated_at
        END
    WHERE id IN (SELECT id FROM reported_unstarted)
    """,
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    # The games were played, so there's nothing to undo.
    pass
