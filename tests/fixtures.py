import contextvars
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
from spellbot.database import (
    DatabaseSession,
    db_session_maker,
    initialize_connection,
    rollback_transaction,
)
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

CLIENT_USER_ID = 1  # id of the test bot itself
OWNER_USER_ID = 2  # id of the test guild owner


@asynccontextmanager
async def _session_context_manager(nosession: bool = False) -> AsyncGenerator[None, None]:
    if nosession:
        yield
        return

    await initialize_connection("spellbot-test", use_transaction=True)

    test_session = db_session_maker()
    DatabaseSession.set(test_session)  # type: ignore

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
async def session_context(request) -> AsyncGenerator[contextvars.Context, None]:
    nosession = "nosession" in request.keywords
    async with _session_context_manager(nosession):
        context = contextvars.copy_context()
        yield context
        for c in context:
            c.set(context[c])


@pytest.fixture(autouse=True)
def use_session_context(session_context: contextvars.Context):
    for cvar in session_context:
        cvar.set(session_context[cvar])
    yield


@pytest.fixture
async def bot() -> AsyncGenerator[SpellBot, None]:
    # In tests we create the connection using fixtures.
    yield build_bot(mock_games=True, create_connection=False)


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
    return GuildFactory.create()


@pytest.fixture
def channel(guild) -> Channel:
    return ChannelFactory.create(guild=guild)


@pytest.fixture
def game(guild, channel) -> Game:
    return GameFactory.create(guild=guild, channel=channel)


@pytest.fixture
def user() -> Game:
    return UserFactory.create()


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
    author,
    offset: int = 1,
) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 4000 + offset
    message.name = f"message-{message.id}"
    message.guild = guild
    message.channel = channel
    message.author = author
    message.reply = AsyncMock()
    message.delete = AsyncMock()
    message.content = "content"
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
    ctx.defer = AsyncMock()

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
def dpy_message(dpy_guild, dpy_channel, dpy_author) -> discord.Message:
    return build_message(dpy_guild, dpy_channel, dpy_author)


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
    return GuildFactory.create(**kwargs)


def channel_from_ctx(ctx_fixture, guild: Guild, **kwargs) -> Channel:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.channel.id)
    return ChannelFactory.create(guild=guild, **kwargs)


def game_from_ctx(ctx_fixture, guild: Guild, channel: Channel, **kwargs) -> Game:
    kwargs["message_xid"] = kwargs.get("message_xid", ctx_fixture.message.id)
    return GameFactory.create(guild=guild, channel=channel, **kwargs)


def user_from_ctx(ctx_fixture, **kwargs) -> User:
    kwargs["xid"] = kwargs.get("xid", ctx_fixture.author.id)
    return UserFactory.create(**kwargs)


def mock_discord_user(user: User) -> discord.User:
    member = MagicMock(spec=discord.User)
    member.id = user.xid
    member.display_name = user.name
    member.mention = f"<@{member.id}>"
    member.send = AsyncMock()
    return member
