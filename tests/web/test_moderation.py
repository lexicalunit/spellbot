from __future__ import annotations

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
        # skipped and the member is not a moderator.
        roles = [{"id": "999", "name": "Admins", "permissions": str(0x8)}]
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
