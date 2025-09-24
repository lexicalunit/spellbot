from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from asgiref.sync import sync_to_async
from dateutil import tz
from dateutil.relativedelta import relativedelta
from sqlalchemy.sql.expression import and_, extract, func, text

from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat
from spellbot.models import Channel, Game, Guild, Play

USER_PAGE_SIZE = 25
CHANNEL_PAGE_SIZE = 10

USER_RECORDS_SQL = r"""
    WITH game_plays AS (
        SELECT
            games.id AS game_id,
            games.updated_at,
            games.channel_xid,
            posts.message_xid,
            games.game_link,
            games.format
        FROM games
        JOIN plays ON plays.game_id = games.id
        JOIN posts ON posts.game_id = games.id
            AND posts.guild_xid = games.guild_xid
            AND posts.channel_xid = games.channel_xid
        WHERE
            games.guild_xid = :guild_xid AND
            plays.user_xid = :user_xid
        ORDER BY games.updated_at DESC
        OFFSET :offset
        LIMIT :page_size
    )
    SELECT
        game_plays.game_id,
        game_plays.updated_at,
        game_plays.channel_xid,
        game_plays.message_xid,
        game_plays.game_link,
        game_plays.format,
        channels.name,
        STRING_AGG(
            CONCAT(
                REPLACE(REPLACE(users.name, ':', ''), '@', ''),
                ':',
                users.xid
            ),
            '@'
            ORDER BY users.xid
        )
    FROM game_plays
    JOIN plays ON plays.game_id = game_plays.game_id
    JOIN users ON users.xid = plays.user_xid
    JOIN channels ON channels.xid = game_plays.channel_xid
    GROUP BY
        game_plays.game_id,
        game_plays.updated_at,
        game_plays.channel_xid,
        game_plays.message_xid,
        game_plays.game_link,
        game_plays.format,
        channels.name
    ORDER BY game_plays.updated_at DESC
    ;
"""

CHANNEL_RECORDS_SQL = r"""
    SELECT
        games.id,
        games.updated_at,
        posts.message_xid,
        games.game_link,
        games.format,
        STRING_AGG(
            CONCAT(
                REPLACE(REPLACE(users.name, ':', ''), '@', ''),
                ':',
                users.xid
            ),
            '@'
            ORDER BY users.xid
        )
    FROM games
    JOIN plays ON plays.game_id = games.id
    JOIN users ON users.xid = plays.user_xid
    JOIN posts ON posts.game_id = games.id
        AND posts.guild_xid = games.guild_xid
        AND posts.channel_xid = games.channel_xid
    WHERE
        games.guild_xid = :guild_xid AND
        games.channel_xid = :channel_xid
    GROUP BY
        games.id,
        games.updated_at,
        posts.message_xid,
        games.game_link,
        games.format
    ORDER BY games.updated_at DESC
    OFFSET :offset
    LIMIT :page_size
    ;
"""


def make_scores(data: str) -> dict[str, Any]:
    scores = {}
    records = data.split("@")
    for record in records:
        name, xid = record.split(":")
        scores[name] = (xid,)
    return scores


def decomposed(combined_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            }
            decomposed_data.append(decomposed_datum)
    return decomposed_data


class PlaysService:
    @sync_to_async()
    def get_plays_by_game_id(self, game_id: int) -> list[Play]:
        return DatabaseSession.query(Play).filter(Play.game_id == game_id).all()

    @sync_to_async()
    def verify_game_pin(self, *, game_id: int, user_xid: int, guild_xid: int, pin: str) -> bool:
        filters = [
            Play.game_id == game_id,
            Play.user_xid == user_xid,
            Play.og_guild_xid == guild_xid,
            Play.pin == pin,
        ]
        if not (play := DatabaseSession.query(Play).filter(and_(*filters)).one_or_none()):
            return False
        play.verified_at = datetime.now(tz=UTC)
        DatabaseSession.commit()
        return True

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

    @sync_to_async()
    def user_records(
        self,
        guild_xid: int,
        user_xid: int,
        page: int = 0,
    ) -> list[dict[str, Any]] | None:
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        if not guild:
            return None

        rows = DatabaseSession.execute(
            text(USER_RECORDS_SQL),
            {
                "guild_xid": guild_xid,
                "user_xid": user_xid,
                "offset": page * USER_PAGE_SIZE,
                "page_size": USER_PAGE_SIZE,
            },
        )
        return [
            {
                "id": row[0],
                "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
                "guild": guild_xid,
                "channel": row[2],
                "message": row[3],
                "link": row[4],
                "format": str(GameFormat(row[5])),
                "guild_name": guild.name,
                "channel_name": row[6],
                "scores": make_scores(row[7]),
            }
            for row in rows
        ]

    @sync_to_async()
    def channel_records(
        self,
        guild_xid: int,
        channel_xid: int,
        page: int = 0,
    ) -> list[dict[str, Any]] | None:
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        if not guild:
            return None
        channel = DatabaseSession.query(Channel).filter(Channel.xid == channel_xid).one_or_none()
        if not channel:
            return None

        rows = DatabaseSession.execute(
            text(CHANNEL_RECORDS_SQL),
            {
                "guild_xid": guild_xid,
                "channel_xid": channel_xid,
                "offset": page * CHANNEL_PAGE_SIZE,
                "page_size": CHANNEL_PAGE_SIZE,
            },
        )
        combined_data = [
            {
                "id": row[0],
                "updated_at": row[1].replace(tzinfo=tz.UTC).timestamp() * 1000,
                "guild": guild_xid,
                "channel": channel_xid,
                "message": row[2],
                "link": row[3],
                "format": str(GameFormat(row[4])),
                "guild_name": guild.name,
                "channel_name": channel.name,
                "scores": make_scores(row[5]),
            }
            for row in rows
        ]
        return decomposed(combined_data)

    @sync_to_async()
    def top_records(
        self,
        guild_xid: int,
        channel_xid: int,
        monthly: bool,
        ago: int,
    ) -> list[tuple[str, Any]]:
        filters = [
            Play.game_id == Game.id,
            Game.guild_xid == guild_xid,
            Game.channel_xid == channel_xid,
        ]
        if monthly:
            target = datetime.now(tz=UTC).date() + relativedelta(months=-ago)
            filters.append(extract("year", Game.started_at) == target.year)
            filters.append(extract("month", Game.started_at) == target.month)
        result = (
            DatabaseSession.query(
                Play.user_xid,
                func.count(Play.game_id).label("count"),
            )
            .filter(*filters)
            .group_by(Play.user_xid)
            .order_by(text("count DESC"))
            .limit(10)
        )
        return result.all()
