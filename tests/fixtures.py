from __future__ import annotations

import asyncio
import contextvars
import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from click.testing import CliRunner
from discord.ext import commands

from spellbot.client import build_bot
from spellbot.database import (
    DatabaseSession,
    db_session_maker,
    delete_test_database,
    initialize_connection,
    rollback_transaction,
)
from spellbot.settings import Settings
from spellbot.web import build_web_app
from tests.factories import (
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildAwardFactory,
    GuildFactory,
    PlayFactory,
    PostFactory,
    QueueFactory,
    TokenFactory,
    UserAwardFactory,
    UserFactory,
    VerifyFactory,
    WatchFactory,
)
from tests.mocks import build_author, build_channel, build_guild, build_interaction, build_message

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator

    import discord
    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from freezegun.api import FrozenDateTimeFactory

    from spellbot import SpellBot
    from spellbot.models import Channel, Game, Guild

logger = logging.getLogger(__name__)


class Factories:
    block = BlockFactory
    channel = ChannelFactory
    game = GameFactory
    guild = GuildFactory
    guild_award = GuildAwardFactory
    play = PlayFactory
    post = PostFactory
    queue = QueueFactory
    user = UserFactory
    user_award = UserAwardFactory
    verify = VerifyFactory
    watch = WatchFactory
    token = TokenFactory


@pytest_asyncio.fixture()
async def factories() -> Factories:
    return Factories()


@pytest_asyncio.fixture
async def session_context(
    request: pytest.FixtureRequest,
    worker_id: str,
) -> contextvars.Context:
    event_loop = asyncio.get_event_loop()

    if "use_db" in request.keywords:  # pragma: no cover
        await initialize_connection("spellbot-test", use_transaction=True, worker_id=worker_id)

        test_session = db_session_maker()
        DatabaseSession.set(test_session)

        BlockFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        ChannelFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        GameFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        GuildAwardFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        GuildFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        PlayFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        PostFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        QueueFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        TokenFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        UserAwardFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        UserFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        VerifyFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore
        WatchFactory._meta.sqlalchemy_session = DatabaseSession  # type: ignore

        def cleanup_session() -> None:
            async def finalizer() -> None:
                try:
                    test_session.close()
                    await rollback_transaction()
                except Exception:  # pragma: no cover
                    logger.exception("Error rolling back transaction")

            event_loop.run_until_complete(finalizer())

        request.addfinalizer(cleanup_session)

    context = contextvars.copy_context()

    def cleanup_context() -> None:
        nonlocal context
        for c in context:
            c.set(context[c])

    request.addfinalizer(cleanup_context)

    return context


@pytest.fixture(scope="session", autouse=True)
def cleanup_databases(
    request: pytest.FixtureRequest,
    worker_id: str,
) -> Generator[None, None, None]:
    yield
    if "use_db" in request.keywords:  # pragma: no cover
        delete_test_database(worker_id)


@pytest_asyncio.fixture(autouse=True)
async def use_session_context(
    request: pytest.FixtureRequest,
    session_context: contextvars.Context,
) -> None:
    if "use_db" in request.keywords:  # pragma: no cover
        for cvar in session_context:
            cvar.set(session_context[cvar])


@pytest_asyncio.fixture
async def bot() -> SpellBot:
    # In tests we create the connection using fixtures.
    return build_bot(mock_games=True, create_connection=False)


@pytest.fixture
def client(
    aiohttp_client: Callable[..., Awaitable[TestClient[web.Request, web.Application]]],
) -> TestClient[web.Request, web.Application]:
    app = build_web_app()
    event_loop = asyncio.get_event_loop()
    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def settings() -> Settings:
    return Settings()


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
def interaction(
    dpy_guild: discord.Guild,
    dpy_channel: discord.TextChannel,
    dpy_author: discord.User,
) -> discord.Interaction:
    return build_interaction(dpy_guild, dpy_channel, dpy_author)


@pytest.fixture
def context(
    dpy_guild: discord.Guild,
    dpy_channel: discord.TextChannel,
    dpy_author: discord.User,
    dpy_message: discord.Message,
) -> discord.Interaction:
    stub = AsyncMock(spec=commands.Context)
    stub.guild = dpy_guild
    stub.channel = dpy_channel
    stub.channel_id = dpy_channel.id
    stub.author = dpy_author
    stub.message = dpy_message
    return stub


@pytest.fixture
def cli() -> Generator[MagicMock, None, None]:
    with (
        patch("spellbot.cli.asyncio") as mock_asyncio,
        patch("spellbot.cli.configure_logging") as mock_configure_logging,
        patch("spellbot.cli.hupper") as mock_hupper,
        patch("spellbot.client.build_bot") as mock_build_bot,
        patch("spellbot.cli.settings") as mock_settings,
        patch("spellbot.web.launch_web_server") as mock_launch_web_server,
    ):
        mock_loop = MagicMock(name="loop")
        mock_loop.run_forever = MagicMock(name="run_forever")
        mock_asyncio.new_event_loop = MagicMock(return_value=mock_loop, name="new_event_loop")
        mock_bot = MagicMock(name="bot")
        mock_bot.run = MagicMock(name="run")
        mock_build_bot.return_value = mock_bot
        mock_hupper.start_reloader = MagicMock(name="start_reloader")
        mock_settings.BOT_TOKEN = "facedeadbeef"
        mock_settings.PORT = 404

        obj = MagicMock()
        obj.asyncio = mock_asyncio
        obj.build_bot = mock_build_bot
        obj.configure_logging = mock_configure_logging
        obj.hupper = mock_hupper
        obj.launch_web_server = mock_launch_web_server
        obj.settings = mock_settings
        obj.bot = mock_bot
        obj.loop = mock_loop
        yield obj


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest_asyncio.fixture(autouse=True)
async def use_consistent_date(freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("1982-04-24")
