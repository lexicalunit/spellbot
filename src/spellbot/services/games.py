from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from dateutil import tz
from ddtrace.trace import tracer
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import and_, asc, column, or_
from sqlalchemy.sql.functions import count

from spellbot.data import PlayerDataDict, QueueData
from spellbot.database import DatabaseSession, any_of
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import (
    Block,
    Channel,
    Game,
    GameStatus,
    Guild,
    Play,
    Post,
    Queue,
    User,
    UserAward,
    Watch,
)
from spellbot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from spellbot.data import GameData


logger = logging.getLogger(__name__)

MAX_GAME_LINK_LEN = Game.game_link.property.columns[0].type.length


@tracer.wrap()
async def get(game_id: int) -> GameData | None:
    """Fetch the game data by game id."""
    game: Game | None = await DatabaseSession.get(Game, game_id)
    return await game.to_data() if game else None


@tracer.wrap()
async def get_by_voice_xid(voice_xid: int) -> GameData | None:
    """Fetch the game data by associated discord voice channel id."""
    stmt = select(Game).where(Game.voice_xid == voice_xid)
    result = await DatabaseSession.execute(stmt)
    game: Game | None = result.scalar_one_or_none()
    return await game.to_data() if game else None


@tracer.wrap()
async def get_by_message_xid(message_xid: int) -> GameData | None:
    """Fetch the game data by associated discord message id."""
    stmt = select(Game).join(Post).where(Post.message_xid == message_xid)
    result = await DatabaseSession.execute(stmt)
    game: Game | None = result.scalar_one_or_none()
    return await game.to_data() if game else None


def to_ms(dt: datetime | None) -> float | None:
    """Convert a naive UTC datetime to millis since epoch, or `None`."""
    if dt is None:
        return None
    return dt.replace(tzinfo=tz.UTC).timestamp() * 1000


@tracer.wrap()
async def game_detail_view(game_id: int) -> dict[str, Any] | None:
    """
    Return a rich dictionary of all information associated with a game.

    Intended for the public game detail web page. Excludes the game `password`
    and per-play `pin` (both are secrets that gate verification).
    """
    game = (
        await DatabaseSession.execute(select(Game).where(Game.id == game_id))
    ).scalar_one_or_none()
    if game is None:
        return None

    guild = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == game.guild_xid))
    ).scalar_one_or_none()
    channel = (
        await DatabaseSession.execute(select(Channel).where(Channel.xid == game.channel_xid))
    ).scalar_one_or_none()

    posts = (
        (
            await DatabaseSession.execute(
                select(Post).where(Post.game_id == game_id).order_by(Post.message_xid),
            )
        )
        .scalars()
        .all()
    )

    plays = (
        (
            await DatabaseSession.execute(
                select(Play).where(Play.game_id == game_id).order_by(Play.user_xid),  # type: ignore
            )
        )
        .scalars()
        .all()
    )

    queues = (
        (
            await DatabaseSession.execute(
                select(Queue).where(Queue.game_id == game_id).order_by(Queue.user_xid),
            )
        )
        .scalars()
        .all()
    )

    user_xids = {p.user_xid for p in plays} | {q.user_xid for q in queues}
    user_names: dict[int, str | None] = {}
    if user_xids:
        users = (
            (
                await DatabaseSession.execute(
                    select(User).where(User.xid.in_(user_xids)),
                )
            )
            .scalars()
            .all()
        )
        user_names = {u.xid: u.name for u in users}

    return {
        "id": game.id,
        "status": GameStatus(game.status).name,
        "format": str(GameFormat(game.format)),
        "bracket": str(GameBracket(game.bracket)),
        "service": str(GameService(game.service)),
        "seats": game.seats,
        "locale": game.locale,
        "blind": game.blind,
        "rules": game.rules,
        "game_link": game.game_link,
        "voice_xid": game.voice_xid,
        "voice_invite_link": game.voice_invite_link,
        "created_at": to_ms(game.created_at),
        "updated_at": to_ms(game.updated_at),
        "started_at": to_ms(game.started_at),
        "deleted_at": to_ms(game.deleted_at),
        "guild": {
            "xid": guild.xid if guild else game.guild_xid,
            "name": guild.name if guild else None,
            "show_links": guild.show_links if guild else False,
        },
        "channel": {
            "xid": channel.xid if channel else game.channel_xid,
            "name": channel.name if channel else None,
        },
        "posts": [
            {
                "guild_xid": post.guild_xid,
                "channel_xid": post.channel_xid,
                "message_xid": post.message_xid,
                "created_at": post.created_at,
                "updated_at": post.updated_at,
            }
            for post in posts
        ],
        "plays": [
            {
                "user_xid": play.user_xid,
                "user_name": user_names.get(play.user_xid),
                "og_guild_xid": play.og_guild_xid,
                "created_at": to_ms(play.created_at),
                "updated_at": to_ms(play.updated_at),
            }
            for play in plays
        ],
        "queued": [
            {
                "user_xid": queue.user_xid,
                "user_name": user_names.get(queue.user_xid),
                "og_guild_xid": queue.og_guild_xid,
            }
            for queue in queues
        ],
    }


async def guild_detail_view(guild_xid: int) -> dict[str, Any] | None:
    """
    Return public guild info plus the channels that have game records.

    Intended for the public guild (server history) web page. Channels are
    ordered by most-recent activity and carry a count of games. This matches the
    channel records page's notion of a "record": a game with a post in that
    channel. Returns `None` when the guild is unknown.
    """
    guild = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))  # type: ignore
    ).scalar_one_or_none()
    if guild is None:
        return None

    games_count = func.count(func.distinct(Game.id)).label("games")
    last_updated_at = func.max(Game.updated_at).label("last_updated_at")
    rows = (
        await DatabaseSession.execute(
            select(
                Channel.xid,  # type: ignore
                Channel.name,
                games_count,
                last_updated_at,
            )
            .select_from(Game)
            .join(Post, Post.game_id == Game.id)
            .join(Channel, Channel.xid == Game.channel_xid)
            .where(Game.guild_xid == guild_xid)
            .group_by(Channel.xid, Channel.name)
            .order_by(last_updated_at.desc()),
        )
    ).all()

    return {
        "guild": {
            "xid": guild.xid,
            "name": guild.name,
            "promote": guild.promote,
        },
        "channels": [
            {
                "xid": int(row[0]),
                "name": row[1],
                "games": int(row[2]),
                "last_updated_at": to_ms(row[3]),
            }
            for row in rows
        ],
    }


@tracer.wrap()
async def add_player(game_data: GameData, player_xid: int) -> GameData:
    """Add the player with the given id to the given game."""
    # Double check that the number of players + 1 doesn't go over the seat limit,
    # this should in theory never happen. If we see this assertion failing, investigate.
    players: int = (
        await DatabaseSession.execute(
            select(func.count()).select_from(Queue).where(Queue.game_id == game_data.id),
        )
    ).scalar() or 0
    assert players + 1 <= game_data.seats

    # upsert into queues
    await DatabaseSession.execute(
        insert(Queue)
        .values(
            [
                {
                    "user_xid": player_xid,
                    "game_id": game_data.id,
                    "og_guild_xid": game_data.guild_xid,
                },
            ],
        )
        .on_conflict_do_nothing(),
    )
    await DatabaseSession.commit()

    # This operation should "dirty" the Game, so we need to update its updated_at.
    query = (
        update(Game)
        .where(Game.id == game_data.id)
        .values(updated_at=datetime.now(tz=UTC))
        .returning(Game)
        .execution_options(synchronize_session="fetch")
    )
    result = await DatabaseSession.execute(query)
    updated_game: Game = result.scalars().one()
    await DatabaseSession.commit()
    return await updated_game.to_data()


@tracer.wrap()
async def upsert(
    *,
    guild_xid: int,
    channel_xid: int,
    author_xid: int,
    friends: list[int],
    seats: int,
    rules: str | None,
    format: int,
    bracket: int,
    service: int,
    locale: str,
    create_new: bool = False,
    blind: bool = False,
    to_mode: bool = False,
) -> tuple[bool, GameData]:
    """Create or update a new game matching the given criteria."""
    existing_game: Game | None = None
    if not create_new:
        existing_game = await _find_existing(
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            author_xid=author_xid,
            friends=friends,
            seats=seats,
            rules=rules,
            format=format,
            bracket=bracket,
            service=service,
            to_mode=to_mode,
        )

    new: bool
    game: Game
    if existing_game:
        game = existing_game
        new = False
    else:
        game = Game(
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            seats=seats,
            rules=rules,
            format=format,
            bracket=bracket,
            service=service,
            blind=blind,
            locale=locale,
        )
        DatabaseSession.add(game)
        await DatabaseSession.commit()
        new = True

    # upsert into queues
    user_xids = [*friends, author_xid]
    await DatabaseSession.execute(
        insert(Queue)
        .values(
            [
                {
                    "user_xid": xid,
                    "game_id": game.id,
                    "og_guild_xid": guild_xid,
                }
                for xid in user_xids
            ],
        )
        .on_conflict_do_nothing(),
    )
    await DatabaseSession.commit()

    return new, await game.to_data()


@tracer.wrap()
async def _find_existing(
    *,
    guild_xid: int,
    channel_xid: int,
    author_xid: int,
    friends: list[int],
    seats: int,
    rules: str | None,
    format: int,
    bracket: int,
    service: int,
    to_mode: bool = False,
) -> Game | None:
    """Find a suitable existing game with the given criteria if one exists."""
    required_seats = 1 + len(friends)

    player_count = count(Queue.user_xid).over(partition_by=Game.id)
    inner = (
        select(
            Game,
            Queue.user_xid,
            player_count.label("player_count"),
        )
        .join(Queue, isouter=True)
        .filter(
            and_(
                Game.guild_xid == guild_xid,
                Game.channel_xid == channel_xid,  # type: ignore
                Game.seats == seats,  # type: ignore
                Game.rules == rules,
                Game.format == format,  # type: ignore
                Game.bracket == bracket,  # type: ignore
                Game.service == service,  # type: ignore
                Game.status == GameStatus.PENDING.value,  # type: ignore
                Game.deleted_at.is_(None),
            ),
        )
        .group_by(Game, Queue.user_xid)
        .order_by(asc(Game.updated_at))
        .alias("inner")
    )
    outer = aliased(Game, inner)
    found_game_stmt = select(outer).where(
        or_(
            column("player_count") == 0,
            and_(
                column("player_count") > 0,
                column("player_count") <= seats - required_seats,
            ),
        ),
    )

    game: Game
    found_games = (await DatabaseSession.execute(found_game_stmt)).scalars().all()

    if to_mode:
        # Tournament organizer mode: user blocks are not enforced in this channel, so
        # the first matching game is always acceptable.
        return found_games[0] if found_games else None

    joiners = [author_xid, *friends]
    xids_blocked_by_joiners = [
        row.blocked_user_xid
        for row in (
            await DatabaseSession.execute(
                select(Block).where(any_of(Block.user_xid, joiners)),
            )
        )
        .scalars()
        .all()
    ]

    # Return the first game that doesn't match up players who have blocked each other
    for game in found_games:
        players = [player.xid for player in await game.players()]
        if any(xid in players for xid in xids_blocked_by_joiners):
            continue  # a joiner has blocked one of the players

        xids_blocked_by_players = [
            row.blocked_user_xid
            for row in (
                await DatabaseSession.execute(
                    select(Block).where(any_of(Block.user_xid, players)),
                )
            )
            .scalars()
            .all()
        ]
        if any(xid in joiners for xid in xids_blocked_by_players):
            continue  # a player has blocked one of the joiners

        return game

    return None


@tracer.wrap()
async def add_post(
    game_data: GameData,
    guild_xid: int,
    channel_xid: int,
    message_xid: int,
) -> GameData:
    """Associate the given game with the given Discord post metadata."""
    query = (
        insert(Post)
        .values(
            [
                {
                    "game_id": game_data.id,
                    "guild_xid": guild_xid,
                    "channel_xid": channel_xid,
                    "message_xid": message_xid,
                },
            ],
        )
        .on_conflict_do_nothing()
        .returning(Post)
    )
    result = await DatabaseSession.execute(query)
    new_post: Post | None = result.scalars().one_or_none()
    await DatabaseSession.commit()
    if new_post is not None:
        game_data.posts.append(new_post.to_data())
    return game_data


@tracer.wrap()
async def other_game_ids(game_data: GameData) -> list[int]:
    """Return the id of any other games with overlapping players."""
    player_xids = [player.xid for player in game_data.players]
    rows = (
        await DatabaseSession.execute(
            select(Queue.game_id).where(
                any_of(Queue.user_xid, player_xids),
                Queue.game_id != game_data.id,
            ),
        )
    ).all()
    return [int(row[0]) for row in rows if row[0]]


@tracer.wrap()
async def shrink_game(game_data: GameData) -> GameData:
    """Shrink the number of seats in a game to the current number of players."""
    query = (
        update(Game)
        .where(Game.id == game_data.id)
        .values(seats=len(game_data.players))
        .returning(Game)
    )
    result = await DatabaseSession.execute(query)
    updated_game: Game = result.scalars().one()
    await DatabaseSession.commit()
    return await updated_game.to_data()


@tracer.wrap()
async def make_ready(
    game_data: GameData,
    game_link: str | None,
    password: str | None,
    pins: list[str],
) -> GameData:
    """Start the pending game."""
    game: Game = await DatabaseSession.get(Game, game_data.id)  # TODO: Refactor to avoid fetch?
    assert len(game_link or "") <= MAX_GAME_LINK_LEN
    queues: list[QueueData] = [
        queue.to_data()
        for queue in (
            await DatabaseSession.execute(
                select(Queue).where(Queue.game_id == game.id),
            )
        )
        .scalars()
        .all()
    ]

    # update game's state
    game.game_link = game_link  # type: ignore  # column is "game_link" for legacy reasons
    game.password = password  # type: ignore
    game.status = GameStatus.STARTED.value
    game.started_at = datetime.now(tz=UTC)  # type: ignore

    if not queues:  # Not sure this is possible, but just in case.
        await DatabaseSession.commit()
        return await game.to_data()

    # upsert into plays
    await DatabaseSession.execute(
        insert(Play)
        .values(
            [
                {
                    "user_xid": queue.user_xid,
                    "game_id": game.id,
                    "og_guild_xid": queue.og_guild_xid,
                    "pin": pins[i],
                }
                for i, queue in enumerate(queues)
            ],
        )
        .on_conflict_do_nothing(),
    )

    # upsert into user_awards
    await DatabaseSession.execute(
        insert(UserAward)
        .values(
            [
                {
                    "guild_xid": game.guild_xid,
                    "user_xid": queue.user_xid,
                }
                for queue in queues
            ],
        )
        .on_conflict_do_nothing(),
    )

    # drop the players from any other queues
    player_xids = [queue.user_xid for queue in queues]
    await DatabaseSession.execute(
        delete(Queue)
        .where(any_of(Queue.user_xid, player_xids))
        .execution_options(synchronize_session=False),
    )

    await DatabaseSession.commit()
    return await game.to_data()


@tracer.wrap()
async def watch_notes(
    game_data: GameData,
    player_xids: list[int],
) -> dict[int, str | None]:
    """Return any moderator watch notes for the given game."""
    watched = (
        (
            await DatabaseSession.execute(
                select(Watch).where(
                    and_(
                        Watch.guild_xid == game_data.guild_xid,
                        any_of(Watch.user_xid, player_xids),
                    ),
                ),
            )
        )
        .scalars()
        .all()
    )
    return {cast("int", watch.user_xid): cast("str | None", watch.note) for watch in watched}


@tracer.wrap()
async def set_voice(
    game_data: GameData,
    *,
    voice_xid: int,
    voice_invite_link: str | None = None,
) -> GameData:
    """Assign the given voice channel information to the given game."""
    query = (
        update(Game)
        .where(Game.id == game_data.id)
        .values(voice_xid=voice_xid, voice_invite_link=voice_invite_link)
        .returning(Game)
    )
    result = await DatabaseSession.execute(query)
    updated_game: Game = result.scalars().one()
    await DatabaseSession.commit()
    return await updated_game.to_data()


@tracer.wrap()
async def blocked(game_data: GameData, user_xid: int) -> bool:
    """Return True iff the given user should not be allowed in the given game."""
    users_author_has_blocked = [
        row.blocked_user_xid
        for row in (
            await DatabaseSession.execute(
                select(Block).where(Block.user_xid == user_xid),
            )
        )
        .scalars()
        .all()
    ]
    users_who_blocked_author = [
        row.user_xid
        for row in (
            await DatabaseSession.execute(
                select(Block).where(Block.blocked_user_xid == user_xid),
            )
        )
        .scalars()
        .all()
    ]
    player_xids = [player.xid for player in game_data.players]
    if any(xid in player_xids for xid in users_author_has_blocked):
        return True
    return any(xid in player_xids for xid in users_who_blocked_author)


@tracer.wrap()
async def games_pending_notification() -> list[GameData]:
    """
    Return pending games eligible for alert notification.

    Games are eligible when they are not started, not deleted, have not yet
    been notified, are at least NOTIFY_GAMES_DELAY_M minutes old, and still
    have at least one open seat.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(minutes=settings.NOTIFY_GAMES_DELAY_M)
    records: Sequence[Game] = (
        (
            await DatabaseSession.execute(
                select(Game)
                .join(Queue, isouter=True)
                .where(
                    Game.status == GameStatus.PENDING.value,  # type: ignore[arg-type]
                    Game.deleted_at.is_(None),
                    Game.started_at.is_(None),
                    Game.notified_at.is_(None),
                    Game.created_at <= cutoff,
                )
                .group_by(Game)
                .having(func.count(Queue.game_id) < Game.seats),
            )
        )
        .scalars()
        .all()
    )
    return [await record.to_data() for record in records]


async def inactive_games(guild_xid: int | None = None) -> list[GameData]:
    """Return any games that should be considered abandoned for inactivity."""
    limit = datetime.now(tz=UTC) - timedelta(minutes=settings.EXPIRE_TIME_M)
    filters = [
        Game.status == GameStatus.PENDING.value,
        Game.deleted_at.is_(None),
    ]
    if guild_xid:
        filters.append(Game.guild_xid == guild_xid)
    records: Sequence[Game] = (
        (
            await DatabaseSession.execute(
                select(Game)
                .join(Queue, isouter=True)
                .where(*filters)
                .group_by(Game)
                .having(
                    or_(
                        Game.updated_at <= limit,
                        func.count(Queue.game_id) == 0,
                    ),
                ),
            )
        )
        .scalars()
        .all()
    )
    return [await record.to_data() for record in records]


@tracer.wrap()
async def delete_games(game_ids: list[int]) -> int:
    """Delete the games with the given ids."""
    query = update(Game).where(any_of(Game.id, game_ids)).values(deleted_at=datetime.now(tz=UTC))
    await DatabaseSession.execute(query)
    result = await DatabaseSession.execute(
        delete(Queue)
        .where(any_of(Queue.game_id, game_ids))
        .execution_options(synchronize_session=False),
    )
    dequeued = result.rowcount
    logger.info("dequeued %s players from games %s", dequeued, game_ids)
    await DatabaseSession.commit()
    return dequeued


@tracer.wrap()
async def message_xids(game_ids: list[int]) -> list[int]:
    """Return the discord post message ids for the given game ids."""
    query = select(
        Post.message_xid,
    ).where(any_of(Post.game_id, game_ids))
    rows = (await DatabaseSession.execute(query)).all()
    return [int(row[0]) for row in rows if row[0]]


@tracer.wrap()
async def dequeue_players(player_xids: list[int]) -> list[int]:
    """Remove the given players from any queues that they're in; returns changed game ids."""
    queues = (
        (
            await DatabaseSession.execute(
                select(Queue).where(any_of(Queue.user_xid, player_xids)),
            )
        )
        .scalars()
        .all()
    )
    game_ids = {cast("int", queue.game_id) for queue in queues}
    for queue in queues:
        await DatabaseSession.delete(queue)
    await DatabaseSession.commit()
    return list(game_ids)


@tracer.wrap()
async def get_last_game(user_xid: int, guild_xid: int) -> GameData | None:
    """Get the last game played by the given user in the given guild."""
    stmt = (
        select(Game)
        .where(
            Game.guild_xid == guild_xid,
            Game.status == GameStatus.STARTED.value,  # type: ignore
            Game.deleted_at.is_(None),
            Play.user_xid == user_xid,
        )
        .join(Play)
        .order_by(Game.created_at.desc())
    )
    last_game = (await DatabaseSession.execute(stmt)).scalars().first()
    return await last_game.to_data() if last_game else None


# A helper function for Convoke game creation. Would be nice to refactor to remove!
@tracer.wrap()
async def player_convoke_data(game_id: int) -> list[PlayerDataDict]:
    """Return the player data for the given game id."""
    stmt = select(Game).where(Game.id == game_id)
    game = (await DatabaseSession.execute(stmt)).scalars().first()
    if not game:
        return []
    return [PlayerDataDict(xid=p.xid, name=p.name) for p in await game.players()]
