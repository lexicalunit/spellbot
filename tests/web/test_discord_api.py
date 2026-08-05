from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import discord
import httpx
import pytest

from spellbot.web.api import discord_api

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

GUILD_XID = 900001
CHANNEL_XID = 900002
USER_XID = 900003
ROLE_XID = 900004
OTHER_ROLE_XID = 900005

VIEW = discord.Permissions(view_channel=True).value
SEND = discord.Permissions(send_messages=True).value
COMMANDS = discord.Permissions(use_application_commands=True).value
ADMIN = discord.Permissions(administrator=True).value
PLAYABLE = VIEW | SEND | COMMANDS


def guild(*, owner_id: str = "1", roles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": str(GUILD_XID),
        "owner_id": owner_id,
        "roles": roles if roles is not None else [{"id": str(GUILD_XID), "permissions": "0"}],
    }


def member(*, roles: list[str] | None = None) -> dict[str, Any]:
    return {"roles": roles or []}


def channel(*, overwrites: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": str(CHANNEL_XID),
        "guild_id": str(GUILD_XID),
        "permission_overwrites": overwrites or [],
    }


def overwrite(
    target: int,
    *,
    kind: int,
    allow: int = 0,
    deny: int = 0,
) -> dict[str, Any]:
    return {"id": str(target), "type": kind, "allow": str(allow), "deny": str(deny)}


@pytest.fixture(autouse=True)
def reset_cache(mocker: MockerFixture) -> None:
    discord_api.cache_clear()
    mocker.patch.object(discord_api.settings, "BOT_TOKEN", "bot-token")


class TestChannelPermissions:
    def test_guild_owner_gets_everything(self) -> None:
        perms = discord_api.channel_permissions(
            guild(owner_id=str(USER_XID)),
            member(),
            # Even an explicit deny can not take anything from the guild owner.
            channel(overwrites=[overwrite(GUILD_XID, kind=0, deny=PLAYABLE)]),
            USER_XID,
        )
        assert perms.view_channel
        assert perms.send_messages
        assert perms.use_application_commands

    def test_administrator_role_gets_everything(self) -> None:
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(ROLE_XID), "permissions": str(ADMIN)}]),
            member(roles=[str(ROLE_XID)]),
            channel(overwrites=[overwrite(GUILD_XID, kind=0, deny=PLAYABLE)]),
            USER_XID,
        )
        assert perms.administrator
        assert perms.send_messages

    def test_everyone_role_applies_without_being_listed_on_the_member(self) -> None:
        # The @everyone role shares the guild id and is never present in member.roles.
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(GUILD_XID), "permissions": str(PLAYABLE)}]),
            member(),
            channel(),
            USER_XID,
        )
        assert perms.view_channel
        assert perms.send_messages
        assert perms.use_application_commands

    def test_roles_the_member_does_not_hold_are_ignored(self) -> None:
        perms = discord_api.channel_permissions(
            guild(
                roles=[
                    {"id": str(GUILD_XID), "permissions": str(VIEW)},
                    {"id": str(OTHER_ROLE_XID), "permissions": str(SEND)},
                ],
            ),
            member(roles=[]),
            channel(),
            USER_XID,
        )
        assert perms.view_channel
        assert not perms.send_messages

    def test_everyone_overwrite_denies(self) -> None:
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(GUILD_XID), "permissions": str(PLAYABLE)}]),
            member(),
            channel(overwrites=[overwrite(GUILD_XID, kind=0, deny=SEND)]),
            USER_XID,
        )
        assert perms.view_channel
        assert not perms.send_messages

    def test_role_overwrite_allow_beats_everyone_deny(self) -> None:
        perms = discord_api.channel_permissions(
            guild(
                roles=[
                    {"id": str(GUILD_XID), "permissions": str(VIEW)},
                    {"id": str(ROLE_XID), "permissions": "0"},
                ],
            ),
            member(roles=[str(ROLE_XID)]),
            channel(
                overwrites=[
                    overwrite(GUILD_XID, kind=0, deny=SEND),
                    overwrite(ROLE_XID, kind=0, allow=SEND),
                ],
            ),
            USER_XID,
        )
        assert perms.send_messages

    def test_member_overwrite_deny_beats_role_overwrite_allow(self) -> None:
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(GUILD_XID), "permissions": str(PLAYABLE)}]),
            member(roles=[str(ROLE_XID)]),
            channel(
                overwrites=[
                    overwrite(ROLE_XID, kind=0, allow=SEND),
                    overwrite(USER_XID, kind=1, deny=SEND),
                ],
            ),
            USER_XID,
        )
        assert perms.view_channel
        assert not perms.send_messages

    def test_a_member_overwrite_is_not_treated_as_a_role_overwrite(self) -> None:
        # A type-1 overwrite whose id happens to be in member.roles must not be folded
        # into the role pass; only its own member pass may apply it.
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(GUILD_XID), "permissions": str(VIEW)}]),
            member(roles=[str(ROLE_XID)]),
            channel(overwrites=[overwrite(ROLE_XID, kind=1, allow=SEND)]),
            USER_XID,
        )
        assert not perms.send_messages

    def test_no_view_channel_collapses_everything(self) -> None:
        # Discord grants nothing in a channel you can not see, whatever the overwrites
        # say, so a send-messages allow must not survive a view-channel denial.
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(GUILD_XID), "permissions": str(PLAYABLE)}]),
            member(),
            channel(overwrites=[overwrite(GUILD_XID, kind=0, deny=VIEW)]),
            USER_XID,
        )
        assert perms.value == 0
        assert not perms.send_messages

    def test_unparsable_permission_values_are_treated_as_zero(self) -> None:
        perms = discord_api.channel_permissions(
            guild(roles=[{"id": str(GUILD_XID), "permissions": "not-a-number"}]),
            member(),
            channel(),
            USER_XID,
        )
        assert perms.value == 0


def make_httpx_client(responses: list[MagicMock]) -> MagicMock:
    """Build a mock httpx.AsyncClient whose `get` returns `responses` in order."""
    inner = MagicMock()
    inner.get = AsyncMock(side_effect=responses)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def response(payload: Any, *, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


@pytest.mark.asyncio
class TestFetch:
    async def test_returns_none_without_a_bot_token(self, mocker: MockerFixture) -> None:
        mocker.patch.object(discord_api.settings, "BOT_TOKEN", None)
        assert await discord_api.fetch("/guilds/1") is None

    async def test_404_is_none(self, mocker: MockerFixture) -> None:
        client = make_httpx_client([response(None, status_code=404)])
        mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        assert await discord_api.fetch("/guilds/1") is None

    async def test_transport_error_is_none(self, mocker: MockerFixture) -> None:
        inner = MagicMock()
        inner.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=inner)
        cm.__aexit__ = AsyncMock(return_value=None)
        mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=cm)
        assert await discord_api.fetch("/guilds/1") is None

    async def test_results_are_cached(self, mocker: MockerFixture) -> None:
        client = make_httpx_client([response(guild())])
        factory = mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        assert await discord_api.get_guild(GUILD_XID) is not None
        assert await discord_api.get_guild(GUILD_XID) is not None
        assert factory.call_count == 1

    async def test_a_missing_member_is_cached_too(self, mocker: MockerFixture) -> None:
        # Negative results must cache as well, or a kicked user re-fetches on every
        # channel of every page render.
        client = make_httpx_client([response(None, status_code=404)])
        factory = mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        assert await discord_api.get_member(GUILD_XID, USER_XID) is None
        assert await discord_api.get_member(GUILD_XID, USER_XID) is None
        assert factory.call_count == 1


@pytest.mark.asyncio
class TestMemberChannelPermissions:
    async def test_resolves_effective_permissions(self, mocker: MockerFixture) -> None:
        client = make_httpx_client(
            [
                response(guild(roles=[{"id": str(GUILD_XID), "permissions": str(PLAYABLE)}])),
                response(member()),
                response(channel()),
            ],
        )
        mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        perms = await discord_api.member_channel_permissions(GUILD_XID, CHANNEL_XID, USER_XID)
        assert perms is not None
        assert perms.send_messages

    async def test_non_member_is_none(self, mocker: MockerFixture) -> None:
        client = make_httpx_client([response(guild()), response(None, status_code=404)])
        mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        perms = await discord_api.member_channel_permissions(GUILD_XID, CHANNEL_XID, USER_XID)
        assert perms is None

    async def test_unresolvable_guild_is_none(self, mocker: MockerFixture) -> None:
        client = make_httpx_client([response(None, status_code=404)])
        mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        perms = await discord_api.member_channel_permissions(GUILD_XID, CHANNEL_XID, USER_XID)
        assert perms is None

    async def test_channel_in_another_guild_is_refused(self, mocker: MockerFixture) -> None:
        # A channel id from a different server must not resolve, or the guild in the URL
        # would decide which permission set gets applied to someone else's channel.
        foreign = channel()
        foreign["guild_id"] = "999999"
        client = make_httpx_client([response(guild()), response(member()), response(foreign)])
        mocker.patch.object(discord_api.httpx, "AsyncClient", return_value=client)
        perms = await discord_api.member_channel_permissions(GUILD_XID, CHANNEL_XID, USER_XID)
        assert perms is None
