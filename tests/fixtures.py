from __future__ import annotations

import asyncio
import contextvars
import itertools
import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, cast, overload
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import freezegun
import pytest
import pytest_asyncio
from click.testing import CliRunner
from discord.ext import commands
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

# Importing registers the audit.activity / audit.transaction tables on Base.metadata so they are
# created and truncated alongside the other tables in the test database.
from spellbot import audit  # noqa: F401
from spellbot.client import build_bot
from spellbot.database import (
    DatabaseSession,
    db_session_maker,
    delete_test_database,
    initialize_connection,
)
from spellbot.database import (
    engine as async_engine,
)
from spellbot.models import Base, Queue
from spellbot.models import User as UserModel
from spellbot.services.guilds import guild_cache
from spellbot.settings import Settings
from spellbot.settings import settings as runtime_settings
from spellbot.web import build_web_app
from tests.factories import (
    AlertFactory,
    BlockFactory,
    ChannelFactory,
    GameFactory,
    GuildAwardFactory,
    GuildFactory,
    GuildMemberFactory,
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
    from freezegun.api import (
        FrozenDateTimeFactory,
        StepTickTimeFactory,
        TickingDateTimeFactory,
    )

    FreezeTimeFactory = FrozenDateTimeFactory | StepTickTimeFactory | TickingDateTimeFactory

    from spellbot import SpellBot
    from spellbot.models import Channel, Game, Guild, User

logger = logging.getLogger(__name__)

# Counters for generating unique offsets in fixtures when running tests in parallel.
# Each worker gets its own counter, and offsets are calculated to avoid collisions
# across workers. Worker gw0 gets offsets 1, 2, 3...; gw1 gets 10001, 10002...; etc.
_fixture_offset_counters: dict[str, itertools.count[int]] = {}
_WORKER_OFFSET_MULTIPLIER = 10000


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
    alert = AlertFactory
    block = BlockFactory
    channel = ChannelFactory
    game = GameFactory
    guild = GuildFactory
    guild_award = GuildAwardFactory
    guild_member = GuildMemberFactory
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
        if async_engine.__wrapped__ is not None:
            await async_engine.__wrapped__.dispose()
        await initialize_connection("spellbot-test", worker_id=worker_id)

        test_session = db_session_maker()
        DatabaseSession.set(test_session)

        sync_db_url = Settings().RESOLVED_DATABASE_URL + f"-{worker_id}"
        sync_engine = create_engine(sync_db_url, isolation_level="AUTOCOMMIT")
        sync_session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)
        sync_session = sync_session_factory()

        def _truncate_all() -> None:
            # Schema-qualify so the audit-schema tables (audit.activity / audit.transaction) are
            # reset between tests too, not just public tables.
            tables = ",".join(
                f'"{t.schema}"."{t.name}"' if t.schema else f'"{t.name}"'
                for t in reversed(Base.metadata.sorted_tables)
            )
            with sync_engine.connect() as conn:
                conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))

        _truncate_all()

        AlertFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        BlockFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        ChannelFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        GameFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        GuildAwardFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        GuildFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        GuildMemberFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        PlayFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        PostFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        QueueFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        TokenFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        UserAwardFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        UserFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        VerifyFactory._meta.sqlalchemy_session = sync_session  # type: ignore
        WatchFactory._meta.sqlalchemy_session = sync_session  # type: ignore

        def cleanup_session() -> None:
            async def finalizer() -> None:
                try:
                    sync_session.close()
                    await test_session.close()
                    _truncate_all()
                    sync_engine.dispose()
                    if async_engine.__wrapped__ is not None:
                        await async_engine.__wrapped__.dispose()
                except Exception:  # pragma: no cover
                    logger.exception("Error cleaning up test session")

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
) -> Generator[None]:
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
    # `setup_admin_sessions` reads `API_BASE_URL` once at construction to decide
    # whether session cookies should be `Secure`. The TestClient binds to
    # `http://127.0.0.1`, so a `Secure` cookie would be dropped on the loopback
    # round-trip and `/admin/login` -> `/admin/oauth/callback` would lose its
    # `oauth_state`. Force an `http://` base URL while the app is built.
    with patch.object(runtime_settings, "API_BASE_URL", "http://127.0.0.1"):
        app = build_web_app()
    event_loop = asyncio.get_event_loop()
    # Disable the test server's access logger: on Python 3.14 aiohttp's access-log
    # time formatter raises (`tm_gmtoff` is None), spamming errors during tests.
    return event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"access_log": None}),
    )


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


@pytest_asyncio.fixture
async def user(interaction: discord.Interaction, add_user: Callable[..., User]) -> User:
    """Get or create a database User that matches the interaction's user."""
    result = await DatabaseSession.execute(
        select(UserModel).where(UserModel.xid == interaction.user.id),
    )
    existing = result.scalars().first()
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


@pytest_asyncio.fixture
async def player(user: User, game: Game) -> User:
    """Put user into a game queue."""
    DatabaseSession.add(Queue(user_xid=user.xid, game_id=game.id, og_guild_xid=game.guild_xid))
    await DatabaseSession.commit()
    return user


@pytest.fixture
def unique_offset(worker_id: str) -> int:
    """
    Generate a unique offset for each test to avoid primary key conflicts in parallel tests.

    Each worker gets its own range of offsets to avoid collisions:
    - master/gw0: 1, 2, 3, ...
    - gw1: 10001, 10002, 10003, ...
    - gw2: 20001, 20002, 20003, ...
    """
    if worker_id not in _fixture_offset_counters:
        # Extract worker number from worker_id (e.g., "gw1" -> 1, "master" -> 0)
        worker_num = 0 if worker_id == "master" else int(worker_id.replace("gw", ""))
        start = worker_num * _WORKER_OFFSET_MULTIPLIER + 1
        _fixture_offset_counters[worker_id] = itertools.count(start)
    return next(_fixture_offset_counters[worker_id])


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


def close_coroutine(coro: Any, **kwargs: Any) -> None:
    coro.close()


@pytest.fixture
def cli() -> Generator[MagicMock]:
    with (
        patch("spellbot.cli.asyncio") as mock_asyncio,
        patch("spellbot.cli.uvloop") as mock_uvloop,
        patch("spellbot.cli.configure_logging") as mock_configure_logging,
        patch("spellbot.cli.configure_tracing") as mock_configure_tracing,
        patch("spellbot.cli.hupper") as mock_hupper,
        patch("spellbot.client.build_bot") as mock_build_bot,
        patch("spellbot.cli.settings") as mock_settings,
        patch("spellbot.web.launch_dev_server") as mock_launch_dev_server,
    ):
        mock_bot = MagicMock(name="bot")
        mock_bot.run = MagicMock(name="run")
        mock_build_bot.return_value = mock_bot
        mock_hupper.start_reloader = MagicMock(name="start_reloader")
        mock_settings.BOT_TOKEN = "facedeadbeef"
        mock_settings.PORT = 404
        mock_settings.LOG_LEVEL = "INFO"
        mock_settings.DISABLE_UVLOOP = False
        mock_uvloop.run = MagicMock(side_effect=close_coroutine)

        obj = MagicMock()
        obj.asyncio = mock_asyncio
        obj.uvloop = mock_uvloop
        obj.build_bot = mock_build_bot
        obj.configure_logging = mock_configure_logging
        obj.configure_tracing = mock_configure_tracing
        obj.hupper = mock_hupper
        obj.launch_dev_server = mock_launch_dev_server
        obj.settings = mock_settings
        obj.bot = mock_bot
        yield obj


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def freezer(request: pytest.FixtureRequest) -> Generator[FreezeTimeFactory]:
    """
    Override pytest-freezer's freezer fixture to use real_asyncio=True.

    This prevents asyncio.sleep() from hanging when time is frozen.
    See https://github.com/spulec/freezegun/issues/383
    """
    marker = request.node.get_closest_marker("freeze_time")
    args = getattr(marker, "args", ())
    kwargs = getattr(marker, "kwargs", {})
    # Enable real_asyncio to prevent asyncio.sleep() from hanging
    kwargs.setdefault("real_asyncio", True)
    with freezegun.freeze_time(*args, **kwargs) as frozen_datetime_factory:
        yield frozen_datetime_factory


@pytest_asyncio.fixture(autouse=True)
async def use_consistent_date(freezer: FreezeTimeFactory) -> None:
    freezer.move_to("1982-04-24")


@pytest.fixture(autouse=True)
def clear_guild_cache() -> None:
    guild_cache.clear()


@pytest.fixture(autouse=True)
def allow_all_dms(request: pytest.FixtureRequest) -> Generator[None]:
    if "no_dm_limiter_patch" in request.keywords:
        yield
        return
    with patch("spellbot.operations.try_consume_dm_slot", new=AsyncMock(return_value=True)):
        yield
