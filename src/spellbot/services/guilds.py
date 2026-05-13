from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.environment import running_in_pytest
from spellbot.models import Channel, Guild, GuildAward

if TYPE_CHECKING:
    import discord

    from spellbot.data import GuildAwardData, GuildData


guild_cache: dict[int, str] = {}


def is_cached(xid: int, name: str) -> bool:  # pragma: no cover
    if running_in_pytest():
        return False
    return bool((cached_name := guild_cache.get(xid)) and cached_name == name)


async def upsert(guild: discord.Guild) -> GuildData | None:
    """Upsert the given Discord guild into the database."""
    name_max_len = Guild.name.property.columns[0].type.length
    raw_name = getattr(guild, "name", "")
    name = raw_name[:name_max_len]
    if not is_cached(guild.id, name):  # pragma: no branch (caching disabled in tests)
        values = {
            "xid": guild.id,
            "name": name,
            "updated_at": datetime.now(tz=UTC),
        }
        upsert = insert(Guild).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Guild.xid],
            index_where=Guild.xid == values["xid"],
            set_={
                "name": upsert.excluded.name,
                "updated_at": upsert.excluded.updated_at,
            },
            where=upsert.excluded.name != Guild.name,
        )
        await DatabaseSession.execute(upsert, values)
        await DatabaseSession.commit()
        guild_cache[guild.id] = name

    result = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild.id))
    ).scalar_one_or_none()
    return await result.to_data() if guild else None


async def set_banned(guild_xid: int, banned: bool) -> None:
    """Mark the given guild as banned from using this bot."""
    values = {
        "xid": guild_xid,
        "name": "Unknown Guild",
        "updated_at": datetime.now(tz=UTC),
        "banned": banned,
    }
    upsert = insert(Guild).values(**values)
    upsert = upsert.on_conflict_do_update(
        index_elements=[Guild.xid],
        index_where=Guild.xid == values["xid"],
        set_={
            "updated_at": upsert.excluded.updated_at,
            "banned": upsert.excluded.banned,
        },
    )
    await DatabaseSession.execute(upsert, values)
    await DatabaseSession.commit()


async def get(guild_xid: int) -> GuildData | None:
    """Fetch the guild data for the given guild xid."""
    guild = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))
    ).scalar_one_or_none()
    return await guild.to_data() if guild else None


async def set_suggest_vc_category(
    guild_data: GuildData,
    category: str | None,
) -> GuildData:
    """Set the suggested voice channel category prefix for the guild."""
    stmt = (
        update(Guild)
        .where(Guild.xid == guild_data.xid)
        .values(suggest_voice_category=category)
        .returning(Guild)
    )
    updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    await DatabaseSession.commit()
    return await updated_guild.to_data()


async def set_motd(guild_data: GuildData, message: str | None = None) -> GuildData:
    """Set the message of the day for the guild."""
    motd = message[: Guild.motd.property.columns[0].type.length] if message else ""
    stmt = update(Guild).where(Guild.xid == guild_data.xid).values(motd=motd).returning(Guild)
    updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    await DatabaseSession.commit()
    return await updated_guild.to_data()


async def toggle_show_links(guild_data: GuildData) -> GuildData:
    """Toggle whether to show SpellTable links in game posts."""
    new_value = not guild_data.show_links
    stmt = (
        update(Guild)
        .where(Guild.xid == guild_data.xid)
        .values(show_links=new_value)
        .returning(Guild)
    )
    updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    await DatabaseSession.commit()
    return await updated_guild.to_data()


async def toggle_voice_create(guild_data: GuildData) -> GuildData:
    """Toggle whether to automatically create voice channels for games."""
    new_value = not guild_data.voice_create
    values: dict[str, bool | None] = {"voice_create": new_value}
    if new_value:
        values["suggest_voice_category"] = None
    stmt = update(Guild).where(Guild.xid == guild_data.xid).values(**values).returning(Guild)
    updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    await DatabaseSession.commit()
    return await updated_guild.to_data()


async def toggle_use_max_bitrate(guild_data: GuildData) -> GuildData:
    """Toggle whether to use maximum bitrate for created voice channels."""
    new_value = not guild_data.use_max_bitrate
    stmt = (
        update(Guild)
        .where(Guild.xid == guild_data.xid)
        .values(use_max_bitrate=new_value)
        .returning(Guild)
    )
    updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    await DatabaseSession.commit()
    return await updated_guild.to_data()


async def voice_category_prefixes(guild_xid: int) -> list[str]:
    """Return distinct voice category prefixes configured across all channels."""
    return [
        str(row[0])
        for row in (
            await DatabaseSession.execute(
                select(Channel.voice_category).where(Channel.guild_xid == guild_xid).distinct(),
            )
        ).all()
    ]


async def voiced() -> list[int]:
    """Return guild xids that have voice channel creation enabled."""
    rows = (
        await DatabaseSession.execute(
            select(Guild.xid).where(Guild.voice_create.is_(True)),
        )
    ).all()
    if not rows:
        return []
    return [int(row[0]) for row in rows]


async def has_award_with_count(guild_xid: int, count: int) -> bool:
    """Check if the guild has an award configured for the given play count."""
    return bool(
        (
            await DatabaseSession.execute(
                select(GuildAward).where(
                    and_(
                        GuildAward.guild_xid == guild_xid,
                        GuildAward.count == count,
                    ),
                ),
            )
        ).scalar_one_or_none(),
    )


async def award_add(
    guild_xid: int,
    count: int,
    role: str,
    message: str,
    **options: bool | None,
) -> GuildAwardData:
    """Add a new award configuration to the guild."""
    repeating = bool(options.get("repeating", False))
    remove = bool(options.get("remove", False))
    verified_only = bool(options.get("verified_only", False))
    unverified_only = bool(options.get("unverified_only", False))
    award = GuildAward(
        guild_xid=guild_xid,
        count=count,
        role=role,
        message=message,
        repeating=repeating,
        remove=remove,
        verified_only=verified_only,
        unverified_only=unverified_only,
    )
    DatabaseSession.add(award)
    await DatabaseSession.commit()
    return award.to_data()


async def award_delete(guild_award_id: int) -> None:
    """Delete the award with the given id."""
    award = await DatabaseSession.get(GuildAward, guild_award_id)
    if award:
        await DatabaseSession.delete(award)
    await DatabaseSession.commit()


async def setup_mythic_track(guild_data: GuildData) -> GuildData:
    """Toggle whether mythic track is enabled for the guild."""
    new_value = not guild_data.enable_mythic_track
    stmt = (
        update(Guild)
        .where(Guild.xid == guild_data.xid)
        .values(enable_mythic_track=new_value)
        .returning(Guild)
    )
    updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    await DatabaseSession.commit()
    return await updated_guild.to_data()
