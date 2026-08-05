from __future__ import annotations

import logging
import time
from typing import Any, Final

import discord
import httpx

from spellbot.settings import settings

logger = logging.getLogger(__name__)

DISCORD_API_ROOT: Final = "https://discord.com/api/v10"

# The web server has no gateway connection, so it reads Discord over REST. Responses are
# cached briefly: short enough that a kick, a ban, or a permission change takes effect
# quickly, long enough that rendering a page does not cost one round-trip per channel.
CACHE_TTL_S: Final = 60.0

# Cache keys are built from ids that come from the encrypted session cookie or from our
# own database, never from unvalidated request input, so one user can neither seed nor
# read another user's entry.
_cache: dict[tuple[str, ...], tuple[Any, float]] = {}

# Resolved once from discord.py so the bit values can never drift from the library the
# bot itself enforces permissions with.
ALL_PERMISSIONS: Final = discord.Permissions.all().value
ADMINISTRATOR: Final = discord.Permissions(administrator=True).value


def cache_get(key: tuple[str, ...]) -> Any:
    """Return a cached value, or `None` when absent or expired."""
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() >= expires_at:
        _cache.pop(key, None)
        return None
    return value


def cache_put(key: tuple[str, ...], value: Any) -> None:
    _cache[key] = (value, time.monotonic() + CACHE_TTL_S)


def cache_clear() -> None:
    """Drop every cached Discord response. Used by tests."""
    _cache.clear()


async def fetch(path: str) -> Any:
    """
    GET a Discord REST resource with the bot token, or `None`.

    Returns `None` both for "not found" and for any transport or status failure, so
    callers fail closed: an unresolvable member or channel is treated as no access.
    """
    if not settings.BOT_TOKEN:
        return None
    headers = {"Authorization": f"Bot {settings.BOT_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{DISCORD_API_ROOT}{path}", headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        logger.warning("could not fetch discord resource %s", path)
        return None


async def get_guild(guild_xid: int) -> dict[str, Any] | None:
    """Fetch a guild, including its role list, or `None`."""
    key = ("guild", str(guild_xid))
    if (cached := cache_get(key)) is not None:
        return cached or None
    guild = await fetch(f"/guilds/{guild_xid}")
    cache_put(key, guild or {})
    return guild


async def get_member(guild_xid: int, user_xid: int) -> dict[str, Any] | None:
    """
    Fetch a guild member, or `None` when they are not in the guild.

    `None` is the answer for someone who was kicked or banned, which is exactly the
    case this whole module exists to catch.
    """
    key = ("member", str(guild_xid), str(user_xid))
    if (cached := cache_get(key)) is not None:
        return cached or None
    member = await fetch(f"/guilds/{guild_xid}/members/{user_xid}")
    cache_put(key, member or {})
    return member


async def get_channel(channel_xid: int) -> dict[str, Any] | None:
    """Fetch a channel, including its permission overwrites, or `None`."""
    key = ("channel", str(channel_xid))
    if (cached := cache_get(key)) is not None:
        return cached or None
    channel = await fetch(f"/channels/{channel_xid}")
    cache_put(key, channel or {})
    return channel


def to_int(value: Any, default: int = 0) -> int:
    """Coerce a Discord API field to an int, falling back to `default`."""
    try:
        return int(value)
    except TypeError, ValueError:
        return default


def base_permissions(guild: dict[str, Any], member: dict[str, Any], user_xid: int) -> int:
    """
    Compute a member's guild-wide permissions from their roles.

    Implements the first half of Discord's documented permission algorithm: the guild
    owner has everything; otherwise take @everyone's permissions unioned with those of
    every role the member holds, and short-circuit to everything on ADMINISTRATOR.
    """
    if to_int(guild.get("owner_id"), default=-1) == user_xid:
        return ALL_PERMISSIONS

    guild_xid = to_int(guild.get("id"))
    # The @everyone role shares the guild id and always applies.
    member_role_ids = {str(role_id) for role_id in member.get("roles", [])}
    member_role_ids.add(str(guild_xid))

    permissions = 0
    for role in guild.get("roles", []):
        if str(role.get("id")) in member_role_ids:
            permissions |= to_int(role.get("permissions"))

    if permissions & ADMINISTRATOR:
        return ALL_PERMISSIONS
    return permissions


def apply_overwrites(
    permissions: int,
    channel: dict[str, Any],
    member: dict[str, Any],
    guild_xid: int,
    user_xid: int,
) -> int:
    """
    Apply a channel's permission overwrites to guild-wide permissions.

    Implements the second half of Discord's algorithm: @everyone's overwrite first, then
    the union of the member's role overwrites (all denies before all allows), then the
    member's own overwrite, which wins outright.
    """
    if permissions & ADMINISTRATOR:
        return ALL_PERMISSIONS

    overwrites = channel.get("permission_overwrites") or []
    by_id = {str(o.get("id")): o for o in overwrites}
    member_role_ids = {str(role_id) for role_id in member.get("roles", [])}

    if everyone := by_id.get(str(guild_xid)):
        permissions &= ~to_int(everyone.get("deny"))
        permissions |= to_int(everyone.get("allow"))

    role_allow = 0
    role_deny = 0
    for overwrite_id, overwrite in by_id.items():
        # Type 0 is a role overwrite, type 1 is a member overwrite.
        if to_int(overwrite.get("type")) != 0 or overwrite_id not in member_role_ids:
            continue
        role_allow |= to_int(overwrite.get("allow"))
        role_deny |= to_int(overwrite.get("deny"))
    permissions &= ~role_deny
    permissions |= role_allow

    if member_overwrite := by_id.get(str(user_xid)):
        permissions &= ~to_int(member_overwrite.get("deny"))
        permissions |= to_int(member_overwrite.get("allow"))

    return permissions


def channel_permissions(
    guild: dict[str, Any],
    member: dict[str, Any],
    channel: dict[str, Any],
    user_xid: int,
) -> discord.Permissions:
    """Return a member's effective permissions in a channel."""
    guild_xid = to_int(guild.get("id"))
    permissions = base_permissions(guild, member, user_xid)
    permissions = apply_overwrites(permissions, channel, member, guild_xid, user_xid)
    resolved = discord.Permissions(permissions)
    # Discord grants nothing in a channel you can not see, regardless of what the
    # overwrites say, so collapse the whole set rather than reporting it piecemeal.
    if not resolved.administrator and not resolved.view_channel:
        return discord.Permissions.none()
    return resolved


async def member_channel_permissions(
    guild_xid: int,
    channel_xid: int,
    user_xid: int,
) -> discord.Permissions | None:
    """
    Resolve a user's effective permissions in a channel, or `None` if we can not.

    `None` means "we could not establish that this user has access" — they are not a
    member, or Discord did not answer — and callers must treat it as a denial.
    """
    guild = await get_guild(guild_xid)
    if guild is None:
        return None
    member = await get_member(guild_xid, user_xid)
    if member is None:
        return None
    channel = await get_channel(channel_xid)
    if channel is None:
        return None
    # Refuse a channel that is not actually in this guild, so a channel id from another
    # server can not be smuggled in via the URL.
    if to_int(channel.get("guild_id"), default=-1) != guild_xid:
        return None
    return channel_permissions(guild, member, channel, user_xid)
