from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from aiohttp.client import ClientSession

from spellbot.client import SpellBot, build_bot
from spellbot.database import DatabaseSession, initialize_connection, rollback_transaction
from spellbot.models.channel import Channel
from spellbot.models.game import Game
from spellbot.models.guild import Guild
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
async def _session_context_manager() -> AsyncGenerator[None, None]:
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


@pytest.fixture
async def session() -> AsyncGenerator[None, None]:
    async with _session_context_manager():
        yield


@pytest.fixture
async def bot() -> AsyncGenerator[SpellBot, None]:
    bot = build_bot(mock_games=True)
    async with _session_context_manager():
        yield bot


@pytest.fixture
def client(loop, aiohttp_client, settings) -> ClientSession:
    app = build_web_app(settings)
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


def build_client_user() -> discord.Member:
    client_user = MagicMock(spec=discord.Member)
    client_user.id = 1
    client_user.display_name = "SpellBot"
    client_user.mention = f"<@{client_user.id}>"
    return client_user


def build_author(offset: int = 1) -> discord.Member:
    author = MagicMock(spec=discord.Member)
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


def build_channel(guild, offset: int = 1) -> discord.TextChannel:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 3000 + offset
    channel.name = f"channel-{channel.id}"
    channel.guild = guild
    return channel


def build_message(guild, channel, author, offset: int = 1) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 4000 + offset
    message.name = f"message-{message.id}"
    message.guild = guild
    message.channel = channel
    message.author = author
    return message


def build_response(guild, channel, offset: int = 1) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 5000 + offset
    message.name = f"message-{message.id}"
    message.guild = guild
    message.channel = channel
    message.author = build_client_user()
    return message


def build_ctx(author, guild, channel, offset: int = 1):
    ctx = MagicMock()
    ctx.author = author
    ctx.author_id = author.id
    ctx.guild = guild
    ctx.guild_id = guild.id
    ctx.channel = channel
    ctx.message = build_message(guild, channel, author, offset)
    ctx.send = AsyncMock(return_value=build_response(guild, channel, offset))
    return ctx


@pytest.fixture
def dpy_author() -> discord.Member:
    return build_author()


@pytest.fixture
def dpy_guild() -> discord.Guild:
    return build_guild()


@pytest.fixture
def dpy_channel(dpy_guild) -> discord.TextChannel:
    return build_channel(dpy_guild)


@pytest.fixture
def ctx(dpy_author, dpy_guild, dpy_channel):
    return build_ctx(dpy_author, dpy_guild, dpy_channel)
