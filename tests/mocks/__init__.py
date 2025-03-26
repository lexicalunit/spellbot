from __future__ import annotations

import importlib
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast, overload
from unittest.mock import AsyncMock, MagicMock

import discord

from spellbot.models import Channel, Guild, User

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

CLIENT_USER_ID = 1  # id of the test bot itself
OWNER_USER_ID = 2  # id of the test guild owner


class MockClient:  # pragma: no cover
    def __init__(
        self,
        *,
        user: discord.User | None = None,
        channels: list[discord.TextChannel] | None = None,
        guilds: list[discord.Guild] | None = None,
        users: list[discord.User] | None = None,
        categories: list[discord.CategoryChannel] | None = None,
    ) -> None:
        self.user = user or MagicMock(spec=discord.User)
        self.channels = channels or []
        self.guilds = guilds or []
        self.users = users or []
        self.categoies = categories or []

    def __get_user(self, xid: int) -> discord.User | None:
        for user in self.users:
            if user.id == xid:
                return user
        return None

    def get_user(self, xid: int) -> discord.User | None:
        return self.__get_user(xid)

    async def fetch_user(self, xid: int) -> discord.User | None:
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


@contextmanager
def mock_operations(
    module: ModuleType,
    users: list[discord.User] | None = None,
) -> Generator[None, None, None]:
    """
    Mock out all operations.py functions found in a given module.

    Special care is given to the mock for `safe_fetch_user()` so that users passed
    into `mock_operations()` will be findable via calls to `safe_fetch_user()`.

    Example usage:

        from spellbot.interactions import lfg_interaction

        with mock_operations(lfg_interaction):
            lfg_interaction.safe_get_partial_message.return_value = MagicMock()
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)
            lfg_interaction.safe_get_partial_message.assert_called_once()

    """
    import pytest

    from spellbot import operations

    _users: list[discord.User] = users or []

    monkeypatch = pytest.MonkeyPatch()
    for name in operations.__dict__:
        if name in module.__dict__:
            if name.startswith("safe_get_"):  # special handling for non-async get
                monkeypatch.setattr(module, name, MagicMock())
            elif name.startswith("safe_"):  # all others we can assume are async
                if name == "safe_fetch_user":

                    async def finder(_: Any, xid: int) -> discord.User | None:
                        return next((user for user in _users if user.id == xid), None)

                    monkeypatch.setattr(module, name, AsyncMock(side_effect=finder))
                else:
                    monkeypatch.setattr(module, name, AsyncMock())

    try:
        yield
    finally:
        importlib.reload(module)


###########################################################
# Discord object builders that build from scratch
###########################################################


# def build_client_user() -> discord.User:
#     client_user = MagicMock(spec=discord.User)
#     client_user.id = CLIENT_USER_ID
#     client_user.display_name = "SpellBot"
#     client_user.mention = f"<@{client_user.id}>"
#     client_user.top_role = None
#     return client_user


def build_author(offset: int = 1) -> discord.User:
    author = MagicMock(spec=discord.User)
    author.id = 1000 + offset
    author.display_name = f"user-{author.id}"
    author.mention = f"<@{author.id}>"
    author.send = AsyncMock()
    author.roles = []
    author.top_role = None
    return author


def build_guild(offset: int = 1) -> discord.Guild:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 2000 + offset
    guild.name = f"guild-{guild.id}"
    guild.owner_id = OWNER_USER_ID
    guild.create_category_channel = AsyncMock()
    guild.bitrate_limit = 64000.0
    return guild


def build_channel(guild: discord.Guild, offset: int = 1) -> discord.TextChannel:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 3000 + offset
    channel.name = f"channel-{channel.id}"
    channel.guild = guild
    channel.type = discord.ChannelType.text
    channel.permissions_for = MagicMock(return_value=discord.Permissions())
    channel.is_set = False
    return channel


def build_message(
    guild: discord.Guild,
    channel: discord.TextChannel,
    author: discord.Member | discord.User,
    offset: int = 1,
) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 4000 + offset
    message.name = f"message-{message.id}"
    message.content = "content"
    message.guild = guild
    message.channel = channel
    message.author = author
    message.reply = AsyncMock()
    message.delete = AsyncMock()
    message.edit = AsyncMock()
    return message


# def build_voice_channel(guild: discord.Guild, offset: int = 1) -> discord.VoiceChannel:
#     channel = MagicMock(spec=discord.VoiceChannel)
#     channel.id = 6000 + offset
#     channel.name = f"voice-channel-{channel.id}"
#     channel.guild = guild
#     return channel


def build_interaction(
    guild: discord.Guild,
    channel: discord.TextChannel,
    author: discord.User,
) -> discord.Interaction:
    stub = AsyncMock(spec=discord.Interaction)
    stub.response = AsyncMock()
    stub.followup = AsyncMock()
    stub.guild = guild
    stub.guild_id = guild.id
    stub.channel = channel
    stub.channel_id = channel.id
    stub.user = author
    stub.original_response = AsyncMock(return_value=build_message(guild, channel, author))
    return stub


###########################################################
# Discord object builders that build from database objects
###########################################################


def mock_discord_user(user: User) -> discord.User:
    member = MagicMock(spec=discord.User)
    member.id = user.xid
    member.display_name = user.name
    member.mention = f"<@{member.id}>"
    member.send = AsyncMock()
    return member


# def mock_discord_channel(
#     channel: Channel,
#     *,
#     guild: discord.Guild | None = None,
# ) -> discord.TextChannel:
#     discord_channel = MagicMock(spec=discord.TextChannel)
#     discord_channel.id = channel.xid
#     discord_channel.type = discord.ChannelType.text
#     discord_channel.name = channel.name
#     if guild:
#         discord_channel.guild = guild
#     else:
#         discord_channel.guild = mock_discord_guild(cast(Guild, channel.guild))
#     discord_channel.fetch_message = AsyncMock()
#     discord_channel.get_partial_message = MagicMock()
#     discord_channel.permissions_for = MagicMock()
#     discord_channel.mention = f"<#{discord_channel.id}>"
#     return discord_channel


def mock_discord_guild(guild: Guild) -> discord.Guild:
    discord_guild = MagicMock(spec=discord.Guild)
    discord_guild.id = guild.xid
    discord_guild.name = guild.name
    discord_guild.bitrate_limit = 64000.0
    return discord_guild


@overload
def mock_discord_object(obj: User) -> discord.User:  # pragma: no cover
    ...


@overload
def mock_discord_object(obj: Channel) -> discord.TextChannel:  # pragma: no cover
    ...


@overload
def mock_discord_object(obj: Guild) -> discord.Guild:  # pragma: no cover
    ...


def mock_discord_object(
    obj: User | Channel | Guild,
) -> discord.User | discord.TextChannel | discord.Guild:
    if isinstance(obj, User):
        return mock_discord_user(obj)
    # if isinstance(obj, Channel):
    #     return mock_discord_channel(obj)
    if isinstance(obj, Guild):
        return mock_discord_guild(obj)
    raise NotImplementedError
