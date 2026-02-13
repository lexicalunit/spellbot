from __future__ import annotations

import asyncio
import contextvars
import itertools
import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, cast, overload
from unittest.mock import AsyncMock, MagicMock, patch

import discord
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
from spellbot.models import Queue
from spellbot.models import User as UserModel
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

    from aiohttp import web
    from aiohttp.test_utils import TestClient
    from discord.app_commands import Command
    from freezegun.api import FrozenDateTimeFactory

    from spellbot import SpellBot
    from spellbot.models import Channel, Game, Guild, User

logger = logging.getLogger(__name__)

# Counter for generating unique offsets in fixtures when running tests in parallel.
# Each test gets a unique offset to avoid primary key conflicts within the same
# transaction (which is shared across all tests in a worker).
_fixture_offset_counter = itertools.count(1)


@overload
def get_last_send_message(  # pragma: no cover
    interaction: discord.Interaction,
    kwarg: Literal["embed"],
) -> dict[str, Any]: ...


@overload
def get_last_send_message(  # pragma: no cover
    interaction: discord.Interaction,
    kwarg: Literal["view"],
) -> list[dict[str, Any]]: ...


@overload
def get_last_send_message(  # pragma: no cover
    interaction: discord.Interaction,
    kwarg: str,
) -> Any: ...


def get_last_send_message(
    interaction: discord.Interaction,
    kwarg: str,
) -> dict[str, Any] | list[dict[str, Any]] | Any:
    """Get the last send_message call's kwargs from an interaction."""
    send_message = interaction.response.send_message
    send_message.assert_called_once()  # type: ignore
    send_message_call = send_message.call_args_list[0]  # type: ignore
    actual = send_message_call.kwargs[kwarg]
    if kwarg == "embed":
        actual = actual.to_dict()
    if kwarg == "view":
        actual = actual.to_components()
    return actual


@overload
def get_last_edit_message(  # pragma: no cover
    interaction: discord.Interaction,
    kwarg: Literal["embed"],
) -> dict[str, Any]: ...


@overload
def get_last_edit_message(  # pragma: no cover
    interaction: discord.Interaction,
    kwarg: Literal["view"],
) -> list[dict[str, Any]]: ...


def get_last_edit_message(
    interaction: discord.Interaction,
    kwarg: str,
) -> dict[str, Any] | list[dict[str, Any]] | Any:
    """Get the last edit_original_response call's kwargs from an interaction."""
    edit_message = interaction.edit_original_response
    edit_message.assert_called_once()  # type: ignore
    edit_message_call = edit_message.call_args_list[0]  # type: ignore
    actual = edit_message_call.kwargs[kwarg]
    if kwarg == "embed":
        actual = actual.to_dict()
    if kwarg == "view":
        actual = actual.to_components()
    return actual


async def run_command[CogT: commands.Cog, **CogCallbackP](
    command: Command[CogT, CogCallbackP, None],
    interaction: discord.Interaction,
    **kwargs: Any,
) -> None:
    """Run a discord.py app command with the given interaction and kwargs."""
    kwargs["interaction"] = interaction
    callback = command.callback
    if command.binding:  # pragma: no cover
        callback = partial(callback, command.binding)
    callback = cast("Callable[..., Awaitable[None]]", callback)
    return await callback(**kwargs)


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
def guild(factories: Factories, interaction: discord.Interaction) -> Guild:
    """Create a database Guild that matches the interaction's guild."""
    assert interaction.guild is not None
    return factories.guild.create(xid=interaction.guild_id, name=interaction.guild.name)


@pytest.fixture
def add_guild(factories: Factories) -> Callable[..., Guild]:
    """Add a guild."""
    return factories.guild.create


@pytest.fixture
def add_channel(factories: Factories, guild: Guild) -> Callable[..., Channel]:
    """Add a channel to the given guild."""
    return partial(factories.channel.create, guild=guild)


@pytest.fixture
def channel(interaction: discord.Interaction, add_channel: Callable[..., Channel]) -> Channel:
    """Create a database Channel that matches the interaction's channel."""
    assert interaction.channel is not None
    assert hasattr(interaction.channel, "name")
    channel_name = interaction.channel.name  # type: ignore
    return add_channel(xid=interaction.channel_id, name=channel_name)


@pytest.fixture
def add_user(factories: Factories) -> Callable[..., User]:
    """Add a user."""
    return factories.user.create


@pytest.fixture
def user(interaction: discord.Interaction, add_user: Callable[..., User]) -> User:
    """Get or create a database User that matches the interaction's user."""
    # Check if a user with this xid already exists (e.g., created by action fixtures)
    existing = DatabaseSession.query(UserModel).filter_by(xid=interaction.user.id).first()
    if existing:
        return existing
    return add_user(xid=interaction.user.id)


@pytest.fixture
def message(interaction: discord.Interaction) -> discord.Message:
    """Create a mock discord.Message for the interaction."""
    assert interaction.guild is not None
    assert interaction.channel is not None
    assert isinstance(interaction.channel, discord.TextChannel)
    return build_message(interaction.guild, interaction.channel, interaction.user)


@pytest.fixture
def game(
    factories: Factories,
    guild: Guild,
    channel: Channel,
    message: discord.Message,
) -> Game:
    """Create a database Game with a post."""
    game = factories.game.create(guild=guild, channel=channel)
    factories.post.create(guild=guild, channel=channel, game=game, message_xid=message.id)
    return game


@pytest.fixture
def player(user: User, game: Game) -> User:
    """Put user into a game queue."""
    DatabaseSession.add(Queue(user_xid=user.xid, game_id=game.id, og_guild_xid=game.guild_xid))
    DatabaseSession.commit()
    return user


@pytest.fixture
def unique_offset() -> int:
    """Generate a unique offset for each test to avoid primary key conflicts in parallel tests."""
    return next(_fixture_offset_counter)


@pytest.fixture
def dpy_author(unique_offset: int) -> discord.User:
    return build_author(offset=unique_offset)


@pytest.fixture
def dpy_guild(unique_offset: int) -> discord.Guild:
    return build_guild(offset=unique_offset)


@pytest.fixture
def dpy_channel(dpy_guild: discord.Guild, unique_offset: int) -> discord.TextChannel:
    return build_channel(dpy_guild, offset=unique_offset)


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
