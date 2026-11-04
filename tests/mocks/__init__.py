# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import sys
from contextlib import contextmanager
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast, overload

import pytest

from spellbot import operations
from spellbot.models import Guild, User
from tests.mocks import decoys
from tests.mocks.girudo import (
    GirudoTestData,
    MockHTTPClient,
    MockHTTPResponse,
    create_mock_channel,
    create_mock_game,
    create_mock_guild,
    create_mock_user,
)
from tests.mocks.ids import CLIENT_USER_ID, OWNER_USER_ID

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    import discord
    from decoy import Decoy


class MockClient:  # pragma: no cover
    def __init__(
        self,
        *,
        user: discord.User | None = None,
        channels: list[discord.TextChannel] | None = None,
        guilds: list[discord.Guild] | None = None,
        users: Sequence[discord.User | discord.Member] | None = None,
        categories: list[discord.CategoryChannel] | None = None,
    ) -> None:
        self.user = user
        self.channels = channels or []
        self.guilds = guilds or []
        self.users = list(users or [])
        self.categories = categories or []

    def __get_user(self, xid: int) -> discord.User | discord.Member | None:
        for user in self.users:
            if user.id == xid:
                return user
        return None

    def get_user(self, xid: int) -> discord.User | discord.Member | None:
        return self.__get_user(xid)

    async def fetch_user(self, xid: int) -> discord.User | discord.Member | None:
        return self.__get_user(xid)

    def __get_channel(self, xid: int) -> discord.TextChannel | None:
        for channel in self.channels:
            if channel.id == xid:
                return channel
        return None

    def get_channel(self, xid: int) -> discord.TextChannel | None:
        return self.__get_channel(xid)

    async def fetch_channel(self, xid: int) -> discord.TextChannel | None:
        return self.__get_channel(xid)

    def __get_guild(self, xid: int) -> discord.Guild | None:
        for guild in self.guilds:
            if guild.id == xid:
                return guild
        return None

    def get_guild(self, xid: int) -> discord.Guild | None:
        return self.__get_guild(xid)

    async def fetch_guild(self, xid: int) -> discord.Guild | None:
        return self.__get_guild(xid)


def mock_client(*args: Any, **kwargs: Any) -> discord.Client:
    return cast("discord.Client", MockClient(*args, **kwargs))


def action_modules(module: ModuleType) -> list[ModuleType]:
    """Every loaded `spellbot.actions` module, plus `module` itself."""
    modules = [
        loaded
        for loaded_name, loaded in sorted(sys.modules.items())
        if loaded_name.startswith("spellbot.actions.") and isinstance(loaded, ModuleType)
    ]
    return modules if module in modules else [*modules, module]


@contextmanager
def mock_operations(
    decoy: Decoy,
    module: ModuleType,
    users: Sequence[discord.User | discord.Member] | None = None,
) -> Generator[None]:
    """
    Fake out all operations.py functions used by a given action module.

    Each fake is a decoy of the real operation, so it keeps its signature and sync/async-ness,
    and returns `None` unless stubbed. `safe_fetch_user()` instead finds the `users` given.

    The fakes replace the real functions in `spellbot.operations` itself and in every
    `spellbot.actions` module that imports them, since an action's work is shared with
    `base_action` and helper modules (such as `game_posts` for `lfg_action`). So tests reach
    them as `operations.safe_x`, typed with the real signature, whichever module makes the call.

    Example usage:

        with mock_operations(decoy, lfg_action):
            decoy.when(operations.safe_get_partial_message(ANY, ANY, ANY)).then_return(message)
            await cog.lfg.func(cog, ctx)
            decoy.verify(await operations.safe_send_channel(interaction, ANY, embed=ANY))

    """
    known_users = list(users or [])
    modules = [operations, *action_modules(module)]

    async def find_user(client: discord.Client, xid: int) -> discord.User | discord.Member | None:
        return next((user for user in known_users if user.id == xid), None)

    monkeypatch = pytest.MonkeyPatch()
    for name, real in list(operations.__dict__.items()):
        users_of = [m for m in modules if name.startswith("safe_") and name in m.__dict__]
        if len(users_of) < 2:
            continue
        fake = find_user if name == "safe_fetch_user" else decoy.mock(func=real)
        for m in users_of:
            monkeypatch.setattr(m, name, fake)

    try:
        yield
    finally:
        monkeypatch.undo()


@overload
def mock_discord_object(decoy: Decoy, obj: User) -> discord.Member: ...


@overload
def mock_discord_object(decoy: Decoy, obj: Guild) -> discord.Guild: ...


def mock_discord_object(decoy: Decoy, obj: User | Guild) -> discord.Member | discord.Guild:
    """Build the Discord object for a database user or guild."""
    if isinstance(obj, User):
        return decoys.from_user(decoy, obj)
    return decoys.from_guild(decoy, obj)


__all__ = [
    "CLIENT_USER_ID",
    "OWNER_USER_ID",
    "GirudoTestData",
    "MockClient",
    "MockHTTPClient",
    "MockHTTPResponse",
    "create_mock_channel",
    "create_mock_game",
    "create_mock_guild",
    "create_mock_user",
    "mock_discord_object",
    "mock_operations",
]
