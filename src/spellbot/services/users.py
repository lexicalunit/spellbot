from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from ddtrace.trace import tracer
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.models import (
    Block,
    Game,
    GuildMember,
    Play,
    Post,
    Queue,
    User,
    UserAward,
    Verify,
    Watch,
)
from spellbot.settings import settings

if TYPE_CHECKING:
    import discord

    from spellbot.data import GameData, UserData


logger = logging.getLogger(__name__)


@tracer.wrap()
async def upsert(
    target: discord.User | discord.Member,
    guild_xid: int | None = None,
) -> UserData:
    """Update or insert the user into the database."""
    assert hasattr(target, "id")
    xid = target.id
    max_name_len = User.name.property.columns[0].type.length
    raw_name = getattr(target, "display_name", "")
    name = raw_name[:max_name_len]
    values = {"xid": xid, "name": name, "updated_at": datetime.now(tz=UTC)}
    upsert = insert(User).values(**values)
    upsert = upsert.on_conflict_do_update(
        index_elements=[User.xid],
        index_where=User.xid == values["xid"],
        set_={
            "name": upsert.excluded.name,
            "updated_at": upsert.excluded.updated_at,
        },
    )
    await DatabaseSession.execute(upsert, values)

    # Upsert GuildMember record if guild_xid is provided
    if guild_xid is not None:
        member_values = {
            "user_xid": xid,
            "guild_xid": guild_xid,
            "updated_at": datetime.now(tz=UTC),
        }
        member_upsert = insert(GuildMember).values(**member_values)
        member_upsert = member_upsert.on_conflict_do_update(
            index_elements=[GuildMember.user_xid, GuildMember.guild_xid],
            index_where=and_(
                GuildMember.user_xid == member_values["user_xid"],
                GuildMember.guild_xid == member_values["guild_xid"],
            ),
            set_={
                "updated_at": member_upsert.excluded.updated_at,
            },
        )
        await DatabaseSession.execute(member_upsert, member_values)

    await DatabaseSession.commit()
    user = await DatabaseSession.get(User, xid)
    return user.to_data()


@tracer.wrap()
async def get(user_xid: int) -> UserData | None:
    """Get the user data for the given user id."""
    user: User | None = (
        await DatabaseSession.execute(select(User).where(User.xid == user_xid))
    ).scalar_one_or_none()
    return user.to_data() if user else None


@tracer.wrap()
async def set_banned(user_xid: int, banned: bool) -> UserData:
    """Mark the given user id as banned from using this bot."""
    values = {
        "xid": user_xid,
        "name": "Unknown User",
        "updated_at": datetime.now(tz=UTC),
        "banned": banned,
    }
    stmt = insert(User).values(**values)
    stmt = (
        stmt.on_conflict_do_update(
            index_elements=[User.xid],
            index_where=User.xid == values["xid"],
            set_={
                "updated_at": stmt.excluded.updated_at,
                "banned": stmt.excluded.banned,
            },
        )
        .values(values)
        .returning(User)
    )
    updated_user: User = (await DatabaseSession.execute(stmt)).scalars().one()
    await DatabaseSession.commit()
    return updated_user.to_data()


@tracer.wrap()
async def set_playgroup_user_id(user_xid: int, playgroup_user_id: int) -> None:
    """Store the Playgroup Live user ID for the given Discord user."""
    await DatabaseSession.execute(
        update(User).where(User.xid == user_xid).values(playgroup_user_id=playgroup_user_id),  # type: ignore
    )
    await DatabaseSession.commit()


@tracer.wrap()
async def current_game_id(user_data: UserData, channel_xid: int) -> int | None:
    """Get the current PENDING game id for the user in the given channel."""
    queue = (
        (
            await DatabaseSession.execute(
                select(Queue)
                .join(Game)
                .join(Post)
                .where(
                    and_(
                        Queue.user_xid == user_data.xid,
                        Post.channel_xid == channel_xid,
                        Game.deleted_at.is_(None),
                    ),
                ),
            )
        )
        .scalars()
        .first()
    )
    return queue.game_id if queue else None


@tracer.wrap()
async def leave_game(user_data: UserData, channel_xid: int) -> list[GameData]:
    """Remove the given user from games in the given channel; Returns affected game data."""
    pending_games = (
        (
            await DatabaseSession.execute(
                select(Queue)
                .join(Game)
                .join(Post)
                .where(
                    and_(
                        Queue.user_xid == user_data.xid,
                        Post.channel_xid == channel_xid,
                        Game.deleted_at.is_(None),
                    ),
                ),
            )
        )
        .scalars()
        .all()
    )
    left_game_ids = [game.game_id for game in pending_games]

    await DatabaseSession.execute(
        delete(Queue).where(
            Queue.user_xid == user_data.xid,
            Queue.game_id.in_(left_game_ids),
        ),
    )
    await DatabaseSession.commit()

    # This operation should "dirty" the Games, so
    # we need to update their updated_at field now.
    query = (
        update(Game)
        .where(Game.id.in_(left_game_ids))
        .values(updated_at=datetime.now(tz=UTC))
        .returning(Game)
        .execution_options(synchronize_session="fetch")
    )
    result = (await DatabaseSession.execute(query)).scalars()
    updated_games: list[GameData] = [await g.to_data() for g in result.all()]
    await DatabaseSession.commit()
    return updated_games


@tracer.wrap()
async def is_waiting(user_data: UserData, channel_xid: int) -> GameData | None:
    """Return the pending game the user is waiting in for the given channel, if any."""
    user: User = await DatabaseSession.get(User, user_data.xid)
    return await user.waiting(channel_xid)


@tracer.wrap()
async def pending_games(user_data: UserData) -> int:
    """Return the number of pending games the user is currently queued in."""
    user: User = await DatabaseSession.get(User, user_data.xid)
    return await user.pending_games()


@tracer.wrap()
async def block(author_xid: int, target_xid: int) -> None:
    """Add a block for the given author, blocking the given target."""
    values = {
        "user_xid": author_xid,
        "blocked_user_xid": target_xid,
    }
    upsert = insert(Block).values(**values)
    upsert = upsert.on_conflict_do_nothing()
    await DatabaseSession.execute(upsert, values)
    await DatabaseSession.commit()


@tracer.wrap()
async def unblock(author_xid: int, target_xid: int) -> None:
    """Remove a block for the given author, unblocking the given target."""
    await DatabaseSession.execute(
        delete(Block)
        .where(
            and_(
                Block.user_xid == author_xid,
                Block.blocked_user_xid == target_xid,
            ),
        )
        .execution_options(synchronize_session=False),
    )
    await DatabaseSession.commit()


@tracer.wrap()
async def watch(guild_xid: int, user_xid: int, note: str | None = None) -> None:
    """Add the given user to the moderator watch list for a guild."""
    values: dict[str, Any] = {
        "guild_xid": guild_xid,
        "user_xid": user_xid,
    }
    upsert = insert(Watch).values(**values)
    if note:
        max_note_len = Watch.note.property.columns[0].type.length
        values["note"] = note[:max_note_len]
        upsert = upsert.on_conflict_do_update(
            constraint="watches_pkey",
            index_where=and_(
                Watch.guild_xid == values["guild_xid"],
                Watch.user_xid == values["user_xid"],
            ),
            set_={"note": upsert.excluded.note},
        )
    else:
        upsert = upsert.on_conflict_do_nothing()
    await DatabaseSession.execute(upsert, values)
    await DatabaseSession.commit()


@tracer.wrap()
async def unwatch(guild_xid: int, user_xid: int) -> None:
    """Remove the given user from the moderator watch list for a guild."""
    await DatabaseSession.execute(
        delete(Watch)
        .where(
            and_(
                Watch.guild_xid == guild_xid,
                Watch.user_xid == user_xid,
            ),
        )
        .execution_options(synchronize_session=False),
    )
    await DatabaseSession.commit()


@tracer.wrap()
async def blocklist(user_xid: int) -> list[UserData]:
    """Return the list of user ids that the given user has blocked."""
    return [
        u.to_data()
        for u in (
            await DatabaseSession.execute(
                select(User)
                .join(Block, User.xid == Block.blocked_user_xid)
                .where(Block.user_xid == user_xid)
                .order_by(User.xid),
            )
        )
        .scalars()
        .all()
    ]


@tracer.wrap()
async def move_user(  # pragma: no cover
    guild_xid: int,
    from_user_xid: int,
    to_user_xid: int,
) -> str | None:
    """Move the data for a given user id to another user id."""
    from_user = (
        await DatabaseSession.execute(select(User).where(User.xid == from_user_xid))
    ).scalar_one_or_none()
    if not from_user:
        return "user not found"

    if (
        (
            await DatabaseSession.execute(
                select(func.count()).select_from(Queue).where(Queue.user_xid == from_user_xid),
            )
        ).scalar()
        or 0
    ) > 0:
        return "user is queued"

    try:
        # upsert new user
        user_values = {
            "xid": to_user_xid,
            "name": from_user.name,
            "banned": from_user.banned,
        }
        logger.info("upsert user: %s", user_values)
        user_upsert = insert(User).values(**user_values)
        user_upsert = user_upsert.on_conflict_do_update(
            index_elements=[User.xid],
            index_where=User.xid == user_values["xid"],
            set_={
                "name": user_upsert.excluded.name,
                "updated_at": user_upsert.excluded.updated_at,
                "banned": user_upsert.excluded.banned,
            },
        )
        await DatabaseSession.execute(user_upsert, user_values)

        # upsert watches
        for watch in (
            (
                await DatabaseSession.execute(
                    select(Watch).where(
                        Watch.user_xid == from_user_xid,
                        Watch.guild_xid == guild_xid,
                    ),
                )
            )
            .scalars()
            .all()
        ):
            watch_values = {
                "guild_xid": watch.guild_xid,
                "user_xid": to_user_xid,
                "note": watch.note,
            }
            logger.info("upsert watch: %s", watch_values)
            watch_upsert = insert(Watch).values(**watch_values)
            watch_upsert = watch_upsert.on_conflict_do_update(
                index_elements=[Watch.guild_xid, Watch.user_xid],
                index_where=and_(
                    Watch.guild_xid == watch_values["guild_xid"],
                    Watch.user_xid == watch_values["user_xid"],
                ),
                set_={
                    "user_xid": to_user_xid,
                    "note": watch_upsert.excluded.note,
                },
            )
            await DatabaseSession.execute(watch_upsert, watch_values)

        # upsert user blocks
        for user_block in (
            (
                await DatabaseSession.execute(
                    select(Block).where(
                        Block.user_xid == from_user_xid,
                    ),
                )
            )
            .scalars()
            .all()
        ):
            user_block_values = {
                "user_xid": to_user_xid,
                "blocked_user_xid": user_block.blocked_user_xid,
            }
            logger.info("upsert block: %s", user_block_values)
            user_block_upsert = insert(Block).values(**user_block_values)
            user_block_upsert = user_block_upsert.on_conflict_do_nothing()
            await DatabaseSession.execute(user_block_upsert, user_block_values)

        # upsert user blocked by
        for user_blocked in (
            (
                await DatabaseSession.execute(
                    select(Block).where(
                        Block.blocked_user_xid == from_user_xid,
                    ),
                )
            )
            .scalars()
            .all()
        ):
            user_blocked_values = {
                "user_xid": user_blocked.user_xid,
                "blocked_user_xid": to_user_xid,
            }
            logger.info("upsert blocked: %s", user_blocked_values)
            user_blocked_upsert = insert(Block).values(**user_blocked_values)
            user_blocked_upsert = user_blocked_upsert.on_conflict_do_nothing()
            await DatabaseSession.execute(user_blocked_upsert, user_blocked_values)

        # upsert verifies
        for verify in (
            (
                await DatabaseSession.execute(
                    select(Verify).where(
                        Verify.guild_xid == guild_xid,
                        Verify.user_xid == from_user_xid,
                    ),
                )
            )
            .scalars()
            .all()
        ):
            verify_values = {
                "guild_xid": verify.guild_xid,
                "user_xid": to_user_xid,
                "verified": verify.verified,
            }
            logger.info("upsert verify: %s", verify_values)
            verify_upsert = insert(Verify).values(**verify_values)
            verify_upsert = verify_upsert.on_conflict_do_update(
                index_elements=[Verify.guild_xid, Verify.user_xid],
                index_where=and_(
                    Verify.guild_xid == verify_values["guild_xid"],
                    Verify.user_xid == verify_values["user_xid"],
                ),
                set_={
                    "user_xid": to_user_xid,
                    "verified": verify_upsert.excluded.verified,
                },
            )
            await DatabaseSession.execute(verify_upsert, verify_values)

        # upsert plays
        for play in (
            (
                await DatabaseSession.execute(
                    select(Play)
                    .join(Game)
                    .where(
                        Play.user_xid == from_user_xid,
                        Game.guild_xid == guild_xid,
                    ),
                )
            )
            .scalars()
            .all()
        ):
            play_values = {
                "user_xid": to_user_xid,
                "game_id": play.game_id,
            }
            logger.info("upsert play: %s", play_values)
            play_upsert = insert(Play).values(**play_values)
            play_upsert = play_upsert.on_conflict_do_update(
                index_elements=[Play.user_xid, Play.game_id],  # type: ignore
                index_where=and_(
                    Play.user_xid == play_values["user_xid"],
                    Play.game_id == play_values["game_id"],
                ),
                set_={
                    "user_xid": to_user_xid,
                },
            )
            await DatabaseSession.execute(play_upsert, play_values)

        # upsert user awards
        for award in (
            (
                await DatabaseSession.execute(
                    select(UserAward).where(
                        UserAward.user_xid == from_user_xid,
                        UserAward.guild_xid == guild_xid,
                    ),
                )
            )
            .scalars()
            .all()
        ):
            award_values = {
                "user_xid": to_user_xid,
                "guild_xid": award.guild_xid,
                "guild_award_id": award.guild_award_id,
            }
            logger.info("upsert award: %s", award_values)
            award_upsert = insert(UserAward).values(**award_values)
            award_upsert = award_upsert.on_conflict_do_update(
                index_elements=[UserAward.user_xid, UserAward.guild_xid],
                index_where=and_(
                    UserAward.user_xid == award_values["user_xid"],
                    UserAward.guild_xid == award_values["guild_xid"],
                ),
                set_={
                    "user_xid": to_user_xid,
                    "guild_award_id": award_upsert.excluded.guild_award_id,
                },
            )
            await DatabaseSession.execute(award_upsert, award_values)

        await DatabaseSession.commit()
    except Exception:
        logger.exception("error moving user")
        await DatabaseSession.rollback()
        return "database error"

    return None


@tracer.wrap()
async def get_players_by_xid(xids: list[int]) -> list[UserData]:
    """Fetch user data for the given list of user ids."""
    return [
        u.to_data()
        for u in (await DatabaseSession.execute(select(User).where(User.xid.in_(xids))))
        .scalars()
        .all()
    ]


async def get_xid_by_name(name: str) -> int | None:
    """Look up a user's xid by their name (case-insensitive)."""
    user = (
        (
            await DatabaseSession.execute(
                select(User).where(func.lower(User.name) == func.lower(name)),
            )
        )
        .scalars()
        .first()
    )
    return user.xid if user else None


@tracer.wrap()
async def blocked_by_count(user_xid: int) -> int:
    """Count how many users have blocked this user."""
    return int(
        (
            await DatabaseSession.execute(
                select(func.count()).select_from(Block).where(Block.blocked_user_xid == user_xid),
            )
        ).scalar()
        or 0,
    )


@tracer.wrap()
async def games_played_count(user_xid: int, guild_xid: int) -> int:
    """Count how many games this user has played in the given guild."""
    return int(
        (
            await DatabaseSession.execute(
                select(func.count())
                .select_from(Play)
                .join(Game)
                .where(
                    and_(
                        Play.user_xid == user_xid,
                        Game.guild_xid == guild_xid,
                    ),
                ),
            )
        ).scalar()
        or 0,
    )


@tracer.wrap()
async def is_watched(user_xid: int, guild_xid: int) -> str | None:
    """Check if user is being watched in this guild, return note if so."""
    watch = (
        await DatabaseSession.execute(
            select(Watch).where(
                and_(
                    Watch.user_xid == user_xid,
                    Watch.guild_xid == guild_xid,
                ),
            ),
        )
    ).scalar_one_or_none()
    return watch.note if watch else None


@tracer.wrap()
async def is_verified(user_xid: int, guild_xid: int) -> bool | None:
    """Check if user is verified in this guild. Returns None if no record exists."""
    verify = (
        await DatabaseSession.execute(
            select(Verify).where(
                and_(
                    Verify.user_xid == user_xid,
                    Verify.guild_xid == guild_xid,
                ),
            ),
        )
    ).scalar_one_or_none()
    return verify.verified if verify else None


@tracer.wrap()
async def play_date_range(
    user_xid: int,
    guild_xid: int,
) -> tuple[datetime | None, datetime | None]:
    """Get the earliest and most recent game start dates for a user in a guild."""
    result = (
        await DatabaseSession.execute(
            select(
                func.min(Game.started_at),
                func.max(Game.started_at),
            )
            .join(Play, Play.game_id == Game.id)  # type: ignore
            .where(
                and_(
                    Play.user_xid == user_xid,
                    Game.guild_xid == guild_xid,
                    Game.started_at.isnot(None),
                ),
            ),
        )
    ).one()
    return result[0], result[1]


@tracer.wrap()
async def filter_blocked_list(author_xid: int, other_xids: list[int]) -> list[int]:
    """Given an author, filters out any blocked players from a list of others."""
    users_author_has_blocked = [
        cast("int", row.blocked_user_xid)
        for row in (
            await DatabaseSession.execute(
                select(Block).where(Block.user_xid == author_xid),
            )
        )
        .scalars()
        .all()
        if row
    ]
    users_who_blocked_author_or_other = [
        cast("int", row.user_xid)
        for row in (
            await DatabaseSession.execute(
                select(Block).where(
                    Block.blocked_user_xid.in_([author_xid, *other_xids]),
                ),
            )
        )
        .scalars()
        .all()
    ]
    return list(
        set(other_xids) - set(users_author_has_blocked) - set(users_who_blocked_author_or_other),
    )


@tracer.wrap()
async def filter_pending_games(user_xids: list[int]) -> list[int]:
    """Remove users from the list if they are already in the max number of pending queues."""
    rows = (
        await DatabaseSession.execute(
            select(
                Queue.user_xid,
                func.count(Queue.user_xid).label("pending"),
            )
            .join(Game)
            .where(Game.deleted_at.is_(None))
            .group_by(Queue.user_xid),
        )
    ).all()
    counts = {row[0]: row[1] for row in rows if row[0]}

    return [
        user_xid
        for user_xid in user_xids
        if counts.get(user_xid, 0) + 1 < settings.MAX_PENDING_GAMES
    ]
