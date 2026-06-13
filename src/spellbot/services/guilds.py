from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_, or_

from spellbot import audit
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Guild, GuildAward, web_editable_columns
from spellbot.settings import settings

if TYPE_CHECKING:
    import discord

    from spellbot.data import GuildAwardData, GuildData


guild_cache: dict[int, tuple[str, str | None, str | None]] = {}


def is_cached(xid: int, name: str, locale: str | None, icon: str | None) -> bool:
    """Return True if the guild xid is cached under the given name, locale, and icon."""
    return guild_cache.get(xid) == (name, locale, icon)


def _guild_icon_url(guild: discord.Guild) -> str | None:
    """Return the Discord CDN URL for a `discord.Guild`'s icon, or None."""
    icon = getattr(guild, "icon", None)
    return str(icon) if icon else None


async def upsert(guild: discord.Guild, locale: str | None = None) -> GuildData | None:
    """Upsert the given Discord guild into the database."""
    name_max_len = Guild.name.property.columns[0].type.length
    icon_max_len = Guild.icon.property.columns[0].type.length
    raw_name = getattr(guild, "name", "")
    name = raw_name[:name_max_len]
    raw_icon = _guild_icon_url(guild)
    icon = raw_icon[:icon_max_len] if raw_icon else None
    if not is_cached(guild.id, name, locale, icon):
        values = {
            "xid": guild.id,
            "name": name,
            "updated_at": datetime.now(tz=UTC),
            "active": True,
            "icon": icon,
        }
        if locale:
            values["locale"] = locale
        upsert = insert(Guild).values(**values)
        set_updates = {
            "name": upsert.excluded.name,
            "updated_at": upsert.excluded.updated_at,
            "active": upsert.excluded.active,
            "icon": upsert.excluded.icon,
        }
        where_clauses = [
            upsert.excluded.name != Guild.name,
            upsert.excluded.active != Guild.active,
            upsert.excluded.icon.is_distinct_from(Guild.icon),
        ]
        if locale:
            set_updates["locale"] = upsert.excluded.locale
            where_clauses.append(upsert.excluded.locale != Guild.locale)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Guild.xid],  # type: ignore
            index_where=Guild.xid == values["xid"],
            set_=set_updates,
            where=or_(*where_clauses),
        )
        await DatabaseSession.execute(upsert, values)
        await DatabaseSession.commit()
        guild_cache[guild.id] = (name, locale, icon)

    result = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild.id))  # type: ignore
    ).scalar_one_or_none()
    return await result.to_data() if guild else None


async def set_icon(guild_xid: int, icon: str | None) -> None:
    """Update the cached Discord icon URL for the given guild."""
    await DatabaseSession.execute(
        update(Guild).where(Guild.xid == guild_xid).values(icon=icon),  # type: ignore
    )
    await DatabaseSession.commit()
    guild_cache.pop(guild_xid, None)


async def fetch_icon_url(guild_xid: int) -> str | None:
    """Fetch the current Discord CDN icon URL for `guild_xid` via the REST API."""
    if not settings.BOT_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_xid}",
                headers={"Authorization": f"Bot {settings.BOT_TOKEN}"},
            )
            resp.raise_for_status()
            icon_hash = resp.json().get("icon")
    except httpx.HTTPError:
        return None
    if not icon_hash:
        return None
    ext = "gif" if icon_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/icons/{guild_xid}/{icon_hash}.{ext}"


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
        index_elements=[Guild.xid],  # type: ignore
        index_where=Guild.xid == values["xid"],
        set_={
            "updated_at": upsert.excluded.updated_at,
            "banned": upsert.excluded.banned,
        },
    )
    await DatabaseSession.execute(upsert, values)
    await DatabaseSession.commit()


async def set_promote(guild_xid: int, promote: bool) -> None:
    """Set whether the given guild may be advertised on public SpellBot pages."""
    await DatabaseSession.execute(
        update(Guild).where(Guild.xid == guild_xid).values(promote=promote),  # type: ignore
    )
    await DatabaseSession.commit()


# Guild columns that guild moderators may edit from the web admin panel, derived from
# the `[web-editable]` marker on each column's `doc`. This is an allow-list so that
# owner-only / internal columns can never be written through the settings form payload.
SETTINGS_FIELDS = web_editable_columns(Guild)


async def update_settings(guild_xid: int, **fields: object) -> None:
    """Update an allow-listed subset of this guild's configurable settings."""
    safe = {key: value for key, value in fields.items() if key in SETTINGS_FIELDS}
    if not safe:
        return
    async with audit.transaction():
        await DatabaseSession.execute(
            update(Guild).where(Guild.xid == guild_xid).values(**safe),  # type: ignore
        )
    guild_cache.pop(guild_xid, None)


async def get(guild_xid: int) -> GuildData | None:
    """Fetch the guild data for the given guild xid."""
    guild = (
        await DatabaseSession.execute(select(Guild).where(Guild.xid == guild_xid))  # type: ignore
    ).scalar_one_or_none()
    return await guild.to_data() if guild else None


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
    """Return guild xids that have voice channel creation enabled and are active."""
    rows = (
        await DatabaseSession.execute(
            select(Guild.xid).where(  # type: ignore
                and_(
                    Guild.voice_create.is_(True),
                    Guild.active.is_(True),
                ),
            ),
        )
    ).all()
    if not rows:
        return []
    return [int(row[0]) for row in rows]


async def set_active(guild_xid: int, active: bool) -> None:
    """Mark the given guild as active or inactive."""
    await DatabaseSession.execute(
        update(Guild).where(Guild.xid == guild_xid).values(active=active),  # type: ignore
    )
    await DatabaseSession.commit()


async def award_list(guild_xid: int) -> list[GuildAwardData]:
    """Return all award configurations for the guild, ordered by required game count."""
    awards = (
        (
            await DatabaseSession.execute(
                select(GuildAward)
                .where(GuildAward.guild_xid == guild_xid)
                .order_by(GuildAward.count, GuildAward.id),
            )
        )
        .scalars()
        .all()
    )
    return [award.to_data() for award in awards]


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


async def award_update(
    guild_xid: int,
    guild_award_id: int,
    count: int,
    role: str,
    message: str,
    **options: bool | None,
) -> GuildAwardData | None:
    """Update an existing award, scoped to its guild. Returns None if it doesn't belong here."""
    award = await DatabaseSession.get(GuildAward, guild_award_id)
    if award is None or award.guild_xid != guild_xid:
        return None
    award.count = count
    award.role = role
    award.message = message
    award.repeating = bool(options.get("repeating", False))
    award.remove = bool(options.get("remove", False))
    award.verified_only = bool(options.get("verified_only", False))
    award.unverified_only = bool(options.get("unverified_only", False))
    await DatabaseSession.commit()
    return award.to_data()


async def award_delete(guild_xid: int, guild_award_id: int) -> bool:
    """Delete an award, scoped to its guild. Returns True when an award was deleted."""
    award = await DatabaseSession.get(GuildAward, guild_award_id)
    if award is None or award.guild_xid != guild_xid:
        return False
    await DatabaseSession.delete(award)
    await DatabaseSession.commit()
    return True


async def setup_mythic_track(guild_data: GuildData) -> GuildData:
    """Toggle whether mythic track is enabled for the guild."""
    new_value = not guild_data.enable_mythic_track
    stmt = (
        update(Guild)
        .where(Guild.xid == guild_data.xid)  # type: ignore
        .values(enable_mythic_track=new_value)
        .returning(Guild)
    )
    async with audit.transaction():
        updated_guild: Guild = (await DatabaseSession.execute(stmt)).scalar_one()
    return await updated_guild.to_data()
