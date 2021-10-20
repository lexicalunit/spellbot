import importlib
import inspect
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from aiohttp.client import ClientSession

from spellbot.client import SpellBot, build_bot
from spellbot.database import DatabaseSession, initialize_connection, rollback_transaction
from spellbot.models.channel import Channel
from spellbot.models.game import Game
from spellbot.models.guild import Guild
from spellbot.models.user import User
from spellbot.settings import Settings
from spellbot.web import build_web_app
from tests.factories.award import GuildAwardFactory, UserAwardFactory
from tests.factories.block import BlockFactory
from tests.factories.channel import ChannelFactory
from tests.factories.game import GameFactory
from tests.factories.guild import GuildFactory
from tests.factories.play import PlayFactory
from tests.factories.user import UserFactory
from tests.factories.verify import VerifyFactory
from tests.factories.watch import WatchFactory


@asynccontextmanager
async def _session_context_manager(nosession: bool = False) -> AsyncGenerator[None, None]:
    if nosession:
        yield
        return

    await initialize_connection("spellbot-test", use_transaction=True)

    BlockFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    ChannelFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    GameFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    GuildAwardFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    GuildFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    PlayFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    UserAwardFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    UserFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    VerifyFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
    WatchFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore

    try:
        yield
    finally:
        await rollback_transaction()


@pytest.fixture(scope="function", autouse=True)
async def session(request) -> AsyncGenerator[None, None]:
    nosession = "nosession" in request.keywords
    async with _session_context_manager(nosession):
        yield


@pytest.fixture
async def bot() -> AsyncGenerator[SpellBot, None]:
    yield build_bot(mock_games=True)


@pytest.fixture
def client(loop, aiohttp_client) -> ClientSession:
    app = build_web_app()
    return loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def frozen_now(freezer) -> Generator[datetime, None, None]:
    now = datetime.utcnow()
    freezer.move_to(now)
    yield now


@pytest.fixture
def guild() -> Guild:
    inst = GuildFactory.create()
    DatabaseSession.commit()
    return inst


@pytest.fixture
def channel(guild) -> Channel:
    inst = ChannelFactory.create(guild=guild)
    DatabaseSession.commit()
    return inst


@pytest.fixture
def game(guild, channel) -> Game:
    inst = GameFactory.create(guild=guild, channel=channel)
    DatabaseSession.commit()
    return inst


@pytest.fixture
def user() -> Game:
    inst = UserFactory.create()
    DatabaseSession.commit()
    return inst


def build_client_user() -> discord.User:
    client_user = MagicMock(spec=discord.User)
    client_user.id = 1
    client_user.display_name = "SpellBot"
    client_user.mention = f"<@{client_user.id}>"
    return client_user


def build_author(offset: int = 1) -> discord.User:
    author = MagicMock(spec=discord.User)
    author.id = 1000 + offset
    author.display_name = f"user-{author.id}"
    author.mention = f"<@{author.id}>"
    author.send = AsyncMock()
    return author


def build_guild(offset: int = 1) -> discord.Guild:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 2000 + offset
    guild.name = f"guild-{guild.id}"
    return guild


def build_channel(guild: discord.Guild, offset: int = 1) -> discord.TextChannel:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 3000 + offset
    channel.name = f"channel-{channel.id}"
    channel.guild = guild
    return channel


def build_message(
    guild: discord.Guild,
    channel: discord.TextChannel,
    author,
    offset: int = 1,
) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 4000 + offset
    message.name = f"message-{message.id}"
    message.guild = guild
    message.channel = channel
    message.author = author
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
):
    ctx = MagicMock()
    ctx.author = author
    ctx.author_id = author.id
    ctx.guild = guild
    ctx.guild_id = guild.id
    ctx.channel = channel
    ctx.channel_id = channel.id
    ctx.message = build_message(guild, channel, author, offset)
    ctx.send = AsyncMock(return_value=build_response(guild, channel, offset))

    def set_origin():
        ctx.origin_message = ctx.message
        ctx.origin_message_id = ctx.message.id

    ctx.set_origin = set_origin
    return ctx


@pytest.fixture
def dpy_author() -> discord.User:
    return build_author()


@pytest.fixture
def dpy_guild() -> discord.Guild:
    return build_guild()


@pytest.fixture
def dpy_channel(dpy_guild) -> discord.TextChannel:
    return build_channel(dpy_guild)


@pytest.fixture
def ctx(dpy_guild, dpy_channel, dpy_author):
    return build_ctx(dpy_guild, dpy_channel, dpy_author)


@contextmanager
def mock_operations(
    module,
    users: Optional[list[discord.User]] = None,
) -> Generator[None, None, None]:
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


def guild_from_ctx(ctx_fixture, **kwargs) -> Guild:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.guild.id)
    guild = GuildFactory.create(**kwargs)
    DatabaseSession.commit()
    return guild


def channel_from_ctx(ctx_fixture, guild: Guild, **kwargs) -> Channel:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.channel.id)
    channel = ChannelFactory.create(guild=guild, **kwargs)
    DatabaseSession.commit()
    return channel


def game_from_ctx(ctx_fixture, guild: Guild, channel: Channel, **kwargs) -> Game:
    kwargs["message_xid"] = kwargs.get("message_xid", ctx_fixture.message.id)
    game = GameFactory.create(
        guild=guild,
        channel=channel,
        **kwargs,
    )
    DatabaseSession.commit()
    return game


def user_from_ctx(ctx_fixture, **kwargs) -> User:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.author.id)
    user = UserFactory.create(**kwargs)
    DatabaseSession.commit()
    return user


def mock_discord_user(user: User) -> discord.User:
    member = MagicMock(spec=discord.User)
    member.id = user.xid
    member.display_name = user.name
    member.mention = f"<@{member.id}>"
    member.send = AsyncMock()
    return member
