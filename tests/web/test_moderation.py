# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from spellbot.web.api import moderation

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def make_httpx_client(responses: list[MagicMock]) -> MagicMock:
    """Build a mock httpx.AsyncClient whose `get` returns `responses` in order."""
    inner = MagicMock()
    inner.get = AsyncMock(side_effect=responses)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def guild_response(owner_id: str, roles: list[dict[str, Any]]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"owner_id": owner_id, "roles": roles})
    return resp


def member_response(role_ids: list[str], *, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"roles": role_ids})
    return resp


@pytest.fixture(autouse=True)
def reset_moderation_cache(mocker: MockerFixture) -> None:
    moderation.mod_cache.clear()
    moderation.mod_inflight.clear()
    moderation.guild_cache.clear()
    mocker.patch.object(moderation.settings, "BOT_TOKEN", "bot-token")


@pytest.mark.asyncio
class TestViewerIsModerator:
    async def test_returns_false_without_bot_token(self, mocker: MockerFixture) -> None:
        mocker.patch.object(moderation.settings, "BOT_TOKEN", None)
        assert await moderation.viewer_is_moderator(1, 100) is False

    async def test_bot_owner_moderates_every_guild(self, mocker: MockerFixture) -> None:
        # The owner is not a member of the guild, yet OWNER_XID overrides everything
        # without any Discord API round-trip.
        mocker.patch.object(moderation.settings, "OWNER_XID", 42)
        client = mocker.patch.object(moderation.httpx, "AsyncClient")
        assert await moderation.viewer_is_moderator(42, 100) is True
        client.assert_not_called()

    async def test_guild_owner_is_moderator(self, mocker: MockerFixture) -> None:
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("1", []), member_response([])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is True

    async def test_administrator_permission_is_moderator(self, mocker: MockerFixture) -> None:
        roles = [{"id": "500", "name": "Staff", "permissions": str(0x8)}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is True

    async def test_ban_members_permission_is_moderator(self, mocker: MockerFixture) -> None:
        roles = [{"id": "500", "name": "Staff", "permissions": str(0x4)}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is True

    async def test_mod_prefix_role_is_moderator(self, mocker: MockerFixture) -> None:
        roles = [{"id": "500", "name": "Moderator Team", "permissions": "0"}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is True

    async def test_plain_member_is_not_moderator(self, mocker: MockerFixture) -> None:
        roles = [{"id": "500", "name": "Members", "permissions": "0"}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is False

    async def test_non_member_is_not_moderator(self, mocker: MockerFixture) -> None:
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", []), member_response([], status_code=404)],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is False

    async def test_http_error_is_not_moderator(self, mocker: MockerFixture) -> None:
        inner = MagicMock()
        inner.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=inner)
        cm.__aexit__ = AsyncMock(return_value=None)
        mocker.patch.object(moderation.httpx, "AsyncClient", return_value=cm)
        assert await moderation.viewer_is_moderator(1, 100) is False

    async def test_result_is_cached(self, mocker: MockerFixture) -> None:
        client = make_httpx_client([guild_response("1", []), member_response([])])
        factory = mocker.patch.object(moderation.httpx, "AsyncClient", return_value=client)
        assert await moderation.viewer_is_moderator(1, 100) is True
        # A second call for the same viewer/guild must not hit the REST API again.
        assert await moderation.viewer_is_moderator(1, 100) is True
        assert factory.call_count == 1

    async def test_role_not_held_by_member_is_skipped(self, mocker: MockerFixture) -> None:
        # The guild has an admin role, but the member does not hold it, so it must be
        # skipped and the member is not a moderator. The guild also defines the role the
        # member does hold, as Discord always returns every role it knows about.
        roles = [
            {"id": "999", "name": "Admins", "permissions": str(0x8)},
            {"id": "500", "name": "Members", "permissions": str(0)},
        ]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is False

    async def test_unparsable_permissions_default_to_zero(self, mocker: MockerFixture) -> None:
        # A role whose permissions value is not coercible to int must not raise; it
        # contributes no permissions, so a plainly-named role is not a moderator.
        roles = [{"id": "500", "name": "Members", "permissions": None}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )
        assert await moderation.viewer_is_moderator(1, 100) is False


class TestModerationCache:
    def test_expired_entry_is_evicted(self, mocker: MockerFixture) -> None:
        clock = mocker.patch.object(moderation.time, "monotonic", return_value=0.0)
        key = (1, 100)
        moderation.cache_put(key, result=True)
        assert moderation.cache_get(key) is True
        # Advance past the TTL: the entry expires, is dropped, and reads as a miss.
        clock.return_value = moderation.MOD_CACHE_TTL_S + 1.0
        assert moderation.cache_get(key) is None
        assert key not in moderation.mod_cache


@pytest.mark.asyncio
class TestModeratorResolutionIsShared:
    """One Discord round-trip per viewer and guild, however many requests arrive at once."""

    async def test_concurrent_lookups_share_one_fetch(self, mocker: MockerFixture) -> None:
        started = 0

        async def slow_fetch(viewer_xid: int, guild_xid: int) -> bool:
            nonlocal started
            started += 1
            await asyncio.sleep(0)
            return True

        mocker.patch.object(moderation, "fetch_is_moderator", slow_fetch)

        results = await asyncio.gather(
            *(moderation.viewer_is_moderator(7, 100) for _ in range(8)),
        )

        assert results == [True] * 8
        assert started == 1

    async def test_inflight_entry_is_released(self, mocker: MockerFixture) -> None:
        mocker.patch.object(moderation, "fetch_is_moderator", AsyncMock(return_value=True))

        await moderation.viewer_is_moderator(8, 100)

        assert moderation.mod_inflight == {}

    async def test_inflight_entry_is_released_on_failure(self, mocker: MockerFixture) -> None:
        mocker.patch.object(
            moderation,
            "fetch_is_moderator",
            AsyncMock(side_effect=RuntimeError("boom")),
        )

        with pytest.raises(RuntimeError):
            await moderation.viewer_is_moderator(9, 100)

        assert moderation.mod_inflight == {}

    async def test_second_call_uses_the_cache_not_a_new_fetch(
        self,
        mocker: MockerFixture,
    ) -> None:
        fetch = AsyncMock(return_value=True)
        mocker.patch.object(moderation, "fetch_is_moderator", fetch)

        assert await moderation.viewer_is_moderator(10, 100) is True
        assert await moderation.viewer_is_moderator(10, 100) is True

        fetch.assert_awaited_once()


@pytest.mark.asyncio
class TestUnresolvableModeratorStatus:
    """A Discord blip denies the request but must not be remembered as a denial."""

    async def test_unreachable_discord_denies_without_caching(
        self,
        mocker: MockerFixture,
    ) -> None:
        fetch = AsyncMock(return_value=None)
        mocker.patch.object(moderation, "fetch_is_moderator", fetch)

        assert await moderation.viewer_is_moderator(11, 100) is False
        assert (11, 100) not in moderation.mod_cache

    async def test_recovers_on_the_next_request(self, mocker: MockerFixture) -> None:
        fetch = AsyncMock(side_effect=[None, True])
        mocker.patch.object(moderation, "fetch_is_moderator", fetch)

        assert await moderation.viewer_is_moderator(12, 100) is False
        assert await moderation.viewer_is_moderator(12, 100) is True

    async def test_http_error_resolves_to_unknown(self, mocker: MockerFixture) -> None:
        inner = MagicMock()
        inner.get = AsyncMock(side_effect=httpx.ConnectError("down"))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=inner)
        cm.__aexit__ = AsyncMock(return_value=None)
        mocker.patch.object(moderation.httpx, "AsyncClient", return_value=cm)

        assert await moderation.fetch_is_moderator(13, 100) is None

    async def test_a_real_non_moderator_is_still_cached(self, mocker: MockerFixture) -> None:
        fetch = AsyncMock(return_value=False)
        mocker.patch.object(moderation, "fetch_is_moderator", fetch)

        assert await moderation.viewer_is_moderator(14, 100) is False
        assert await moderation.viewer_is_moderator(14, 100) is False

        fetch.assert_awaited_once()


@pytest.mark.asyncio
class TestGuildRolesCache:
    """Role definitions are shared between viewers, so they are fetched once per guild."""

    async def test_second_viewer_reuses_the_cached_guild(self, mocker: MockerFixture) -> None:
        roles = [{"id": "500", "name": "Staff", "permissions": str(0x8)}]
        client = make_httpx_client(
            [
                guild_response("2", roles),
                member_response(["500"]),
                member_response(["500"]),  # only the member half is fetched again
            ],
        )
        mocker.patch.object(moderation.httpx, "AsyncClient", return_value=client)

        assert await moderation.viewer_is_moderator(1, 100) is True
        assert await moderation.viewer_is_moderator(2, 100) is True

        assert client.__aenter__.return_value.get.await_count == 3

    async def test_expired_guild_entry_is_refetched(self, mocker: MockerFixture) -> None:
        roles = [{"id": "500", "name": "Staff", "permissions": str(0x8)}]
        moderation.guild_cache[100] = ({"owner_id": "2", "roles": []}, time.monotonic() - 1)
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [guild_response("2", roles), member_response(["500"])],
            ),
        )

        assert await moderation.viewer_is_moderator(1, 100) is True

    async def test_guild_cache_get_returns_none_when_absent(self) -> None:
        assert moderation.guild_cache_get(12345) is None

    async def test_expired_entry_is_evicted(self) -> None:
        moderation.guild_cache[777] = ({"owner_id": "1", "roles": []}, time.monotonic() - 1)
        assert moderation.guild_cache_get(777) is None
        assert 777 not in moderation.guild_cache


class TestRolesAreStale:
    """A role id we can not name means the snapshot predates it."""

    def test_known_roles_are_not_stale(self) -> None:
        guild = {"roles": [{"id": "1"}, {"id": "2"}]}
        assert moderation.roles_are_stale(guild, {"1", "2"}) is False

    def test_no_roles_held_is_not_stale(self) -> None:
        assert moderation.roles_are_stale({"roles": []}, set()) is False

    def test_unknown_role_is_stale(self) -> None:
        assert moderation.roles_are_stale({"roles": [{"id": "1"}]}, {"1", "9"}) is True


@pytest.mark.asyncio
class TestNewRoleIsPickedUpImmediately:
    """The long TTL must not delay a brand new Moderator role."""

    async def test_unknown_role_triggers_a_refetch(self, mocker: MockerFixture) -> None:
        # The cached snapshot predates the role the viewer was just given, so a stale
        # cache would deny them for the whole TTL. The refetch sees the new role instead.
        moderation.guild_cache_put(100, {"owner_id": "2", "roles": []})
        fresh = [{"id": "500", "name": "Moderator Team", "permissions": str(0)}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [member_response(["500"]), guild_response("2", fresh)],
            ),
        )

        assert await moderation.viewer_is_moderator(1, 100) is True

    async def test_refetch_replaces_the_cached_guild(self, mocker: MockerFixture) -> None:
        moderation.guild_cache_put(100, {"owner_id": "2", "roles": []})
        fresh = [{"id": "500", "name": "Moderator Team", "permissions": str(0)}]
        mocker.patch.object(
            moderation.httpx,
            "AsyncClient",
            return_value=make_httpx_client(
                [member_response(["500"]), guild_response("2", fresh)],
            ),
        )

        await moderation.viewer_is_moderator(1, 100)

        cached = moderation.guild_cache_get(100)
        assert cached is not None
        assert cached["roles"] == fresh
