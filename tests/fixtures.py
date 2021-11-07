import contextvars
from asyncio import AbstractEventLoop
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import discord
import pytest
from aiohttp.client import ClientSession
from discord_slash.context import InteractionContext

from spellbot.client import SpellBot, build_bot
from spellbot.database import (
    DatabaseSession,
    db_session_maker,
    initialize_connection,
    rollback_transaction,
)
from spellbot.models import Channel, Game, Guild
from spellbot.settings import Settings
from spellbot.web import build_web_app
from tests.factories import (
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildAwardFactory,
    GuildFactory,
    PlayFactory,
    UserAwardFactory,
    UserFactory,
    VerifyFactory,
    WatchFactory,
)
from tests.mocks import build_author, build_channel, build_ctx, build_guild, build_message


class Factories:
    block = BlockFactory
    channel = ChannelFactory
    game = GameFactory
    guild = GuildFactory
    guild_award = GuildAwardFactory
    play = PlayFactory
    user = UserFactory
    user_award = UserAwardFactory
    verify = VerifyFactory
    watch = WatchFactory


@pytest.fixture
async def factories() -> Factories:
    return Factories()


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
async def session_context(request: Any) -> AsyncGenerator[contextvars.Context, None]:
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
def client(loop: AbstractEventLoop, aiohttp_client) -> ClientSession:
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
def guild(factories: Factories) -> Guild:
    return factories.guild.create()


@pytest.fixture
def channel(factories: Factories, guild: Guild) -> Channel:
    return factories.channel.create(guild=guild)


@pytest.fixture
def game(factories: Factories, guild: Guild, channel: Channel) -> Game:
    return factories.game.create(guild=guild, channel=channel)


@pytest.fixture
def user(factories: Factories) -> Game:
    return factories.user.create()


@pytest.fixture
def dpy_author() -> discord.User:
    return build_author()


@pytest.fixture
def dpy_guild() -> discord.Guild:
    return build_guild()


@pytest.fixture
def dpy_channel(dpy_guild: discord.Guild) -> discord.TextChannel:
    return build_channel(dpy_guild)


@pytest.fixture
def dpy_message(
    dpy_guild: discord.Guild,
    dpy_channel: discord.TextChannel,
    dpy_author: discord.User,
) -> discord.Message:
    return build_message(dpy_guild, dpy_channel, dpy_author)


@pytest.fixture
def ctx(
    dpy_guild: discord.Guild,
    dpy_channel: discord.TextChannel,
    dpy_author: discord.User,
) -> InteractionContext:
    return build_ctx(dpy_guild, dpy_channel, dpy_author, origin=False)


@pytest.fixture
def origin_ctx(
    dpy_guild: discord.Guild,
    dpy_channel: discord.TextChannel,
    dpy_author: discord.User,
) -> InteractionContext:
    return build_ctx(dpy_guild, dpy_channel, dpy_author, origin=True)
