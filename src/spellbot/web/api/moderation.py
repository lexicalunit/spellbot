# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Final

import httpx

from spellbot.settings import settings
from spellbot.utils import is_moderator

if TYPE_CHECKING:
    from collections.abc import Awaitable

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

# Lookups currently in flight, so that concurrent requests for the same viewer and guild
# share one Discord round-trip instead of each making their own. Entries live only for the
# duration of the request that created them.
mod_inflight: dict[tuple[int, int], Awaitable[bool | None]] = {}

# A guild's role definitions are identical for every viewer of that guild and change only
# when a role is created, renamed or re-permissioned, so this is the half of the lookup worth
# holding on to. Granting someone an existing role is NOT a change to this data - that shows
# up in the member lookup, which is never cached - so this TTL does not delay a new
# moderator. It only bounds how long a brand new or renamed role could go unrecognised, and
# `roles_are_stale` catches that case immediately anyway.
GUILD_CACHE_TTL_S: Final = 3600.0
guild_cache: dict[int, tuple[dict[str, Any], float]] = {}


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


def guild_cache_get(guild_xid: int) -> dict[str, Any] | None:
    entry = guild_cache.get(guild_xid)
    if entry is None:
        return None
    guild, expires_at = entry
    if time.monotonic() >= expires_at:
        guild_cache.pop(guild_xid, None)
        return None
    return guild


def guild_cache_put(guild_xid: int, guild: dict[str, Any]) -> None:
    guild_cache[guild_xid] = (guild, time.monotonic() + GUILD_CACHE_TTL_S)


def roles_are_stale(guild: dict[str, Any], member_role_ids: set[str]) -> bool:
    """
    Whether the viewer holds a role this snapshot of the guild has never heard of.

    A role id we can not name means the snapshot predates the role, so someone has just
    created or renamed one. Refetching on that signal is what lets the TTL be long: a brand
    new `Moderator` role starts working on the viewer's next request rather than in an hour.
    """
    known = {str(role.get("id")) for role in guild.get("roles", [])}
    return not member_role_ids.issubset(known)


async def fetch_guild(
    client: httpx.AsyncClient,
    guild_xid: int,
    headers: dict[str, str],
) -> dict[str, Any]:
    response = await client.get(
        f"https://discord.com/api/v10/guilds/{guild_xid}",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


async def resolve_once(key: tuple[int, int], viewer_xid: int, guild_xid: int) -> bool | None:
    """
    Resolve one (viewer, guild) pair, sharing a single Discord round-trip between callers.

    A dashboard issues several requests at once, and they all used to miss the cache
    together and each call Discord, so one page view could fire a dozen identical lookups
    and rate limit itself. The first caller owns the request and the rest await its result.
    """
    inflight = mod_inflight.get(key)
    if inflight is not None:
        return await inflight
    task = asyncio.ensure_future(fetch_is_moderator(viewer_xid, guild_xid))
    mod_inflight[key] = task
    try:
        return await task
    finally:
        mod_inflight.pop(key, None)


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
    result = await resolve_once(key, viewer_xid, guild_xid)
    if result is None:
        # Could not reach Discord. Deny this request, but do not remember the denial: a
        # cached failure would lock a real moderator out for the whole TTL over one blip.
        return False
    cache_put(key, result)
    return result


async def fetch_is_moderator(viewer_xid: int, guild_xid: int) -> bool | None:
    """Ask Discord whether the viewer moderates the guild, or None if it could not be asked."""
    if not settings.BOT_TOKEN:
        return False
    headers = {"Authorization": f"Bot {settings.BOT_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            guild = guild_cache_get(guild_xid)
            if guild is None:
                guild = await fetch_guild(client, guild_xid, headers)
                guild_cache_put(guild_xid, guild)
            member_resp = await client.get(
                f"https://discord.com/api/v10/guilds/{guild_xid}/members/{viewer_xid}",
                headers=headers,
            )
            if member_resp.status_code == 404:
                return False  # the viewer is not a member of this guild
            member_resp.raise_for_status()
            member = member_resp.json()
            held_role_ids = {str(role_id) for role_id in member.get("roles", [])}
            if roles_are_stale(guild, held_role_ids):
                guild = await fetch_guild(client, guild_xid, headers)
                guild_cache_put(guild_xid, guild)
    except httpx.HTTPError:
        logger.warning(
            "could not resolve moderator status for viewer %s in guild %s",
            viewer_xid,
            guild_xid,
        )
        return None

    return decide_moderator(guild, held_role_ids, viewer_xid=viewer_xid, guild_xid=guild_xid)


def decide_moderator(
    guild: dict[str, Any],
    held_role_ids: set[str],
    *,
    viewer_xid: int,
    guild_xid: int,
) -> bool:
    """Apply SpellBot's moderator rules to a guild payload and the roles the viewer holds."""
    owner_id = guild.get("owner_id")
    is_guild_owner = owner_id is not None and int(owner_id) == viewer_xid

    # The @everyone role shares the guild id and always applies to every member.
    member_role_ids = held_role_ids | {str(guild_xid)}

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
