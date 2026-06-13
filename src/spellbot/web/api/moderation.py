from __future__ import annotations

import logging
import time
from typing import Final

import httpx

from spellbot.settings import settings
from spellbot.utils import is_moderator

logger = logging.getLogger(__name__)

# Discord permission bit flags we care about for moderator detection.
PERMISSION_ADMINISTRATOR: Final = 0x8
PERMISSION_BAN_MEMBERS: Final = 0x4

# Cache moderator decisions keyed by (viewer_xid, guild_xid). The viewer xid is read
# from the encrypted admin/viewer session cookie, never from client-supplied input, so
# one user can not seed or read another user's entry (no permission spoofing). Entries
# expire so that role/permission changes on Discord are picked up within the TTL.
MOD_CACHE_TTL_S: Final = 300.0
mod_cache: dict[tuple[int, int], tuple[bool, float]] = {}


def cache_get(key: tuple[int, int]) -> bool | None:
    entry = mod_cache.get(key)
    if entry is None:
        return None
    result, expires_at = entry
    if time.monotonic() >= expires_at:
        mod_cache.pop(key, None)
        return None
    return result


def cache_put(key: tuple[int, int], result: bool) -> None:
    mod_cache[key] = (result, time.monotonic() + MOD_CACHE_TTL_S)


async def viewer_is_moderator(viewer_xid: int, guild_xid: int) -> bool:
    """
    Return True when `viewer_xid` is a moderator/admin of `guild_xid`.

    Resolves the viewer's roles and the guild's roles via the Discord REST API using
    the bot token, then applies the same rules as the bot's `user_can_moderate`. The
    decision is cached (see `MOD_CACHE_TTL_S`) to avoid an API round-trip per request.
    """
    if settings.OWNER_XID is not None and viewer_xid == settings.OWNER_XID:
        return True
    key = (viewer_xid, guild_xid)
    cached = cache_get(key)
    if cached is not None:
        return cached
    result = await fetch_is_moderator(viewer_xid, guild_xid)
    cache_put(key, result)
    return result


async def fetch_is_moderator(viewer_xid: int, guild_xid: int) -> bool:
    if not settings.BOT_TOKEN:
        return False
    headers = {"Authorization": f"Bot {settings.BOT_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            guild_resp = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_xid}",
                headers=headers,
            )
            guild_resp.raise_for_status()
            member_resp = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_xid}/members/{viewer_xid}",
                headers=headers,
            )
            if member_resp.status_code == 404:
                return False  # the viewer is not a member of this guild
            member_resp.raise_for_status()
    except httpx.HTTPError:
        logger.warning(
            "could not resolve moderator status for viewer %s in guild %s",
            viewer_xid,
            guild_xid,
        )
        return False

    guild = guild_resp.json()
    member = member_resp.json()

    owner_id = guild.get("owner_id")
    is_guild_owner = owner_id is not None and int(owner_id) == viewer_xid

    # The @everyone role shares the guild id and always applies to every member.
    member_role_ids = {str(role_id) for role_id in member.get("roles", [])}
    member_role_ids.add(str(guild_xid))

    has_admin = False
    has_ban_members = False
    role_names: list[str] = []
    for role in guild.get("roles", []):
        if str(role.get("id")) not in member_role_ids:
            continue
        role_names.append(role.get("name", ""))
        try:
            perms = int(role.get("permissions", 0))
        except TypeError, ValueError:
            perms = 0
        if perms & PERMISSION_ADMINISTRATOR:
            has_admin = True
        if perms & PERMISSION_BAN_MEMBERS:
            has_ban_members = True

    return is_moderator(
        is_guild_owner=is_guild_owner,
        has_admin=has_admin,
        has_ban_members=has_ban_members,
        role_names=role_names,
    )
