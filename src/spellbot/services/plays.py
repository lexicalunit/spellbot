# pylint: disable=wrong-import-order

from asgiref.sync import sync_to_async
from dateutil import tz
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.expression import and_, text

from ..database import DatabaseSession
from ..models import Game, GameFormat, Play

CHANNEL_FILTER = "games.channel_xid = :channel_xid"
USER_FILTER = "plays.user_xid = :user_xid"
PAGE_SIZE = 100

RECORDS_SQL = """
    WITH game_plays AS (
        SELECT
            plays.game_id,
            games.updated_at,
            games.guild_xid,
            games.channel_xid,
            games.message_xid,
            games.spelltable_link,
            games.format
        FROM plays
        JOIN games ON games.id = plays.game_id
        WHERE
            games.guild_xid = :guild_xid AND
            {secondary_filter}
        ORDER BY
            games.updated_at DESC
    )
    SELECT
        game_plays.game_id,
        game_plays.updated_at,
        game_plays.guild_xid,
        game_plays.channel_xid,
        game_plays.message_xid,
        game_plays.spelltable_link,
        game_plays.format,
        guilds.name,
        channels.name,
        STRING_AGG(
            CONCAT(
                REPLACE(REPLACE(users.name, ':', ''), '@', ''),
                ':',
                users.xid,
                ':',
                COALESCE(plays.points, 0)::text
            ),
            '@'
            ORDER BY users.xid
        )
    FROM
        game_plays
        JOIN plays ON plays.game_id = game_plays.game_id
        JOIN users ON users.xid = plays.user_xid
        JOIN channels ON channels.xid = game_plays.channel_xid
        JOIN guilds on guilds.xid = game_plays.guild_xid
    GROUP BY
        game_plays.game_id,
        game_plays.updated_at,
        game_plays.guild_xid,
        game_plays.channel_xid,
        game_plays.message_xid,
        game_plays.spelltable_link,
        game_plays.format,
        guilds.name,
        channels.name
    ORDER BY game_plays.updated_at DESC
    OFFSET :offset
    LIMIT :page_size
    ;
"""


class PlaysService:
    @sync_to_async()
    def count(self, user_xid: int, guild_xid: int) -> int:
        return int(
            DatabaseSession.query(Play)
            .join(Game)
            .filter(
                and_(
                    Play.user_xid == user_xid,
                    Game.guild_xid == guild_xid,
                ),
            )
            .count()
            or 0,
        )

    def _records(
        self,
        sql: TextClause,
        params: dict,
        combined_scores: bool,
    ) -> list[dict]:
        def make_scores(data: str) -> dict:
            scores = {}
            records = data.split("@")
            for record in records:
                name, xid, points = record.split(":")
                scores[name] = (xid, points)
            return scores

        rows = DatabaseSession.execute(sql, params)
        combined_data = [
            {
                "id": row[0],
                "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
                "guild": row[2],
                "channel": row[3],
                "message": row[4],
                "link": row[5],
                "format": str(GameFormat(row[6])),
                "guild_name": row[7],
                "channel_name": row[8],
                "scores": make_scores(row[9]),
            }
            for row in rows
        ]
        if combined_scores:
            return combined_data
        decomposed_data = []
        for data in combined_data:
            for name, score_data in data["scores"].items():
                decomposed_datum = {
                    "id": data["id"],
                    "updated_at": data["updated_at"],
                    "guild": data["guild"],
                    "channel": data["channel"],
                    "message": data["message"],
                    "link": data["link"],
                    "format": data["format"],
                    "guild_name": data["guild_name"],
                    "channel_name": data["channel_name"],
                    "user_name": name,
                    "user_xid": score_data[0],
                    "user_points": score_data[1],
                }
                decomposed_data.append(decomposed_datum)
        return decomposed_data

    @sync_to_async()
    def user_records(
        self,
        guild_xid: int,
        user_xid: int,
        page: int = 0,
    ) -> list[dict]:
        return self._records(
            text(RECORDS_SQL.replace("{secondary_filter}", USER_FILTER)),
            dict(
                guild_xid=guild_xid,
                user_xid=user_xid,
                offset=page * PAGE_SIZE,
                page_size=PAGE_SIZE,
            ),
            combined_scores=True,
        )

    @sync_to_async()
    def channel_records(
        self,
        guild_xid: int,
        channel_xid: int,
        page: int = 0,
    ) -> list[dict]:
        return self._records(
            text(RECORDS_SQL.replace("{secondary_filter}", CHANNEL_FILTER)),
            dict(
                guild_xid=guild_xid,
                channel_xid=channel_xid,
                offset=page * PAGE_SIZE,
                page_size=PAGE_SIZE,
            ),
            combined_scores=False,
        )
