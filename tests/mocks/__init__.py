# pylint: disable=inconsistent-return-statements

import importlib
import inspect
from asyncio import AbstractEventLoop
from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, Union, cast
from unittest.mock import AsyncMock, MagicMock

import discord
from discord_slash.context import InteractionContext

from spellbot.models import Channel, Game, Guild, User
from tests.factories import ChannelFactory, GameFactory, GuildFactory, UserFactory

CLIENT_USER_ID = 1  # id of the test bot itself
OWNER_USER_ID = 2  # id of the test guild owner


class MockClient:
    def __init__(
        self,
        *,
        user: discord.User = MagicMock(spec=discord.User),
        loop: AbstractEventLoop = MagicMock(spec=AbstractEventLoop),
        channels: list[discord.TextChannel] = None,
        guilds: list[discord.Guild] = None,
        users: list[discord.User] = None,
        categories: list[discord.CategoryChannel] = None,
    ):
        self.user = user
        self.loop = loop
        self.channels = channels or []
        self.guilds = guilds or []
        self.users = users or []
        self.categoies = categories or []

    def __get_user(self, xid) -> Optional[discord.User]:
        for user in self.users:
            if user.id == xid:
                return user

    def get_user(self, xid) -> Optional[discord.User]:
        return self.__get_user(xid)

    async def fetch_user(self, xid) -> Optional[discord.User]:
        return self.__get_user(xid)

    def __get_channel(self, xid) -> Optional[discord.TextChannel]:
        for channel in self.channels:
            if channel.id == xid:
                return channel

    def get_channel(self, xid) -> Optional[discord.TextChannel]:
        return self.__get_channel(xid)

    async def fetch_channel(self, xid) -> Optional[discord.TextChannel]:
        return self.__get_channel(xid)

    def __get_guild(self, xid) -> Optional[discord.Guild]:
        for guild in self.guilds:
            if guild.id == xid:
                return guild

    def get_guild(self, xid) -> Optional[discord.Guild]:
        return self.__get_guild(xid)

    async def fetch_guild(self, xid) -> Optional[discord.Guild]:
        return self.__get_guild(xid)


def mock_client(*args, **kwargs) -> discord.Client:
    return cast(discord.Client, MockClient(*args, **kwargs))


@contextmanager
def mock_operations(
    module,
    users: Optional[list[discord.User]] = None,
) -> Generator[None, None, None]:
    """
    Mocks out all operations.py functions found in a given module.

    Special care is given to the mock for `safe_fetch_user()` so that users passed
    into `mock_operations()` will be findable via calls to `safe_fetch_user()`.

    Example usage:

        from spellbot.interactions import lfg_interaction

        with mock_operations(lfg_interaction):
            lfg_interaction.safe_fetch_message.return_value = MagicMock()
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)
            lfg_interaction.safe_fetch_message.assert_called_once()

    """
    from _pytest.monkeypatch import MonkeyPatch

    from spellbot import operations

    _users: list[discord.User] = users or []

    monkeypatch = MonkeyPatch()
    for name, item in operations.__dict__.items():
        if inspect.iscoroutinefunction(item):
            if name in module.__dict__:
                if name == "safe_fetch_user":

                    async def finder(_, xid):
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


def build_client_user() -> discord.User:
    client_user = MagicMock(spec=discord.User)
    client_user.id = CLIENT_USER_ID
    client_user.display_name = "SpellBot"
    client_user.mention = f"<@{client_user.id}>"
    return client_user


def build_author(offset: int = 1) -> discord.User:
    author = MagicMock(spec=discord.User)
    author.id = 1000 + offset
    author.display_name = f"user-{author.id}"
    author.mention = f"<@{author.id}>"
    author.send = AsyncMock()
    author.roles = []
    return author


def build_guild(offset: int = 1) -> discord.Guild:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 2000 + offset
    guild.name = f"guild-{guild.id}"
    guild.owner_id = OWNER_USER_ID
    return guild


def build_channel(guild: discord.Guild, offset: int = 1) -> discord.TextChannel:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 3000 + offset
    channel.name = f"channel-{channel.id}"
    channel.guild = guild
    channel.type = discord.ChannelType.text
    channel.permissions_for = MagicMock(return_value=discord.Permissions())
    return channel


def build_message(
    guild: discord.Guild,
    channel: discord.TextChannel,
    author: Union[discord.Member, discord.User],
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


def build_response(
    guild: discord.Guild,
    channel: discord.TextChannel,
    offset: int = 1,
) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 5000 + offset
    message.name = f"message-{message.id}"
    message.guild = guild
    message.channel = channel
    message.author = build_client_user()
    return message


def build_voice_channel(guild: discord.Guild, offset: int = 1) -> discord.VoiceChannel:
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 6000 + offset
    channel.name = f"voice-channel-{channel.id}"
    channel.guild = guild
    return channel


def build_ctx(
    guild: discord.Guild,
    channel: discord.TextChannel,
    author: discord.User,
    offset: int = 1,
    origin: bool = False,
) -> InteractionContext:
    ctx = MagicMock(spec=InteractionContext)
    ctx.author = author
    ctx.author_id = author.id
    ctx.guild = guild
    ctx.guild_id = guild.id
    ctx.channel = channel
    ctx.channel_id = channel.id
    ctx.message = build_message(guild, channel, author, offset)
    ctx.send = AsyncMock(return_value=build_response(guild, channel, offset))
    ctx.defer = AsyncMock()

    if origin:
        ctx.edit_origin = AsyncMock()
        ctx.origin_message = ctx.message
        ctx.origin_message_id = ctx.message.id

    return ctx


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


def mock_discord_channel(
    channel: Channel,
    *,
    guild: Optional[discord.Guild] = None,
) -> discord.TextChannel:
    discord_channel = MagicMock(spec=discord.TextChannel)
    discord_channel.id = channel.xid
    discord_channel.type = discord.ChannelType.text
    discord_channel.name = channel.name
    if guild:
        discord_channel.guild = guild
    else:
        discord_channel.guild = mock_discord_guild(channel.guild)
    discord_channel.fetch_message = AsyncMock()
    discord_channel.permissions_for = MagicMock()
    discord_channel.mention = f"<#{discord_channel.id}>"
    return discord_channel


def mock_discord_guild(guild: Guild) -> discord.Guild:
    discord_guild = MagicMock(spec=discord.Guild)
    discord_guild.id = guild.xid
    discord_guild.name = guild.name
    return discord_guild


###########################################################
# Database object builders that build from a ctx
###########################################################


def ctx_guild(ctx_fixture, **kwargs) -> Guild:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.guild.id)
    return GuildFactory.create(**kwargs)


def ctx_channel(ctx_fixture, guild: Guild, **kwargs) -> Channel:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.channel.id)
    return ChannelFactory.create(guild=guild, **kwargs)


def ctx_game(ctx_fixture, guild: Guild, channel: Channel, **kwargs) -> Game:
    kwargs["message_xid"] = kwargs.get("message_xid", ctx_fixture.message.id)
    return GameFactory.create(guild=guild, channel=channel, **kwargs)


def ctx_user(ctx_fixture, **kwargs) -> User:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.author.id)
    return UserFactory.create(**kwargs)
