# pylint: disable=too-many-arguments
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import discord
import pytest
import pytest_asyncio
import pytz
from pytest_mock import MockerFixture
from spellbot import SpellBot
from spellbot.actions import TasksAction
from spellbot.client import build_bot
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild
from spellbot.services import GamesService, GuildsService, ServicesRegistry

from tests.fixtures import Factories
from tests.mocks import mock_discord_object


@pytest_asyncio.fixture(autouse=True)
def use_log_level_info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)


@pytest_asyncio.fixture(autouse=True)
def use_mock_sleep(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("asyncio.sleep", new_callable=AsyncMock)


@pytest_asyncio.fixture
async def mock_services() -> MagicMock:
    services = MagicMock(spec=ServicesRegistry)
    services.games = MagicMock(spec=GamesService)
    services.guilds = MagicMock(spec=GuildsService)
    services.guilds.voiced = AsyncMock()
    return services


@pytest_asyncio.fixture
async def action(bot: SpellBot) -> TasksAction:
    async with TasksAction.create(bot) as action:
        return action


@pytest_asyncio.fixture
async def guild(factories: Factories) -> Guild:
    return factories.guild.create(voice_create=True)


@pytest_asyncio.fixture
async def discord_guild(guild: Guild, mocker: MockerFixture) -> discord.Guild:
    discord_obj: discord.Guild = mock_discord_object(guild)  # type: ignore
    mocker.patch("spellbot.client.SpellBot.get_guild", return_value=discord_obj)
    discord_obj.categories = []  # type: ignore
    return discord_obj


@pytest_asyncio.fixture
async def channel(factories: Factories, guild: Guild) -> Channel:
    return factories.channel.create(guild=guild)


@pytest_asyncio.fixture
async def game(factories: Factories, guild: Guild, channel: Channel) -> Game:
    return factories.game.create(guild=guild, channel=channel)


@pytest_asyncio.fixture
async def make_voice_channel(
    discord_guild: discord.Guild,
) -> Callable[..., discord.VoiceChannel]:
    def factory(
        id: int,
        name: str,
        perms: discord.Permissions,
        created_at: datetime,
    ) -> discord.VoiceChannel:
        voice = MagicMock(spec=discord.VoiceChannel)
        voice.id = id
        voice.name = name
        voice.guild = discord_guild
        voice.type = discord.ChannelType.voice
        voice.permissions_for = MagicMock(return_value=perms)
        voice.created_at = created_at
        return voice

    return factory


@pytest_asyncio.fixture
async def make_category_channel(
    discord_guild: discord.Guild,
) -> Callable[..., discord.CategoryChannel]:
    def factory(
        id: int,
        name: str,
        perms: discord.Permissions,
        voice_channels: list[discord.VoiceChannel],
    ) -> discord.CategoryChannel:
        category = MagicMock(spec=discord.CategoryChannel)
        category.id = id
        category.name = name
        category.guild = discord_guild
        category.type = discord.ChannelType.category
        category.permissions_for = MagicMock(return_value=perms)
        category.voice_channels = voice_channels
        discord_guild.categories.append(category)  # type: ignore
        return category

    return factory


@pytest_asyncio.fixture
async def bot(mocker: MockerFixture, discord_guild: discord.Guild) -> SpellBot:
    mocker.patch(
        "spellbot.client.SpellBot.guilds",
        new_callable=PropertyMock,
        return_value=[discord_guild],
    )
    return build_bot(mock_games=True, create_connection=False)


@pytest.mark.asyncio()
class TestTaskCleanupOldVoiceChannels:
    async def test_when_nothing_exists(
        self,
        action: TasksAction,
        mock_services: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        action.services = mock_services
        await action.cleanup_old_voice_channels()
        mock_services.guilds.voiced.assert_called_once_with()
        assert "starting task cleanup_old_voice_channels" in caplog.text

    async def test_when_exception_raised(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(action, "gather_channels", AsyncMock(side_effect=RuntimeError))
        await action.cleanup_old_voice_channels()
        assert "error: exception in background task:" in caplog.text

    async def test_when_guild_is_not_active(
        self,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
    ) -> None:
        factories.guild.create(voice_create=True)
        mocker.patch(
            "spellbot.client.SpellBot.guilds",
            new_callable=PropertyMock,
            return_value=[],
        )
        bot = build_bot(mock_games=True, create_connection=False)
        async with TasksAction.create(bot) as action:
            await action.cleanup_old_voice_channels()
        assert "guild is not active" in caplog.text

    async def test_when_guild_is_not_cached(
        self,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(voice_create=True)
        mocker.patch(
            "spellbot.client.SpellBot.guilds",
            new_callable=PropertyMock,
            return_value=[mock_discord_object(guild)],
        )
        bot = build_bot(mock_games=True, create_connection=False)
        async with TasksAction.create(bot) as action:
            await action.cleanup_old_voice_channels()
        assert "could not get guild from discord.py cache" in caplog.text

    async def test_when_guild_has_no_categories(
        self,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(voice_create=True)
        discord_guild = mock_discord_object(guild)
        mocker.patch(
            "spellbot.client.SpellBot.guilds",
            new_callable=PropertyMock,
            return_value=[discord_guild],
        )
        mocker.patch(
            "spellbot.client.SpellBot.get_guild",
            return_value=discord_guild,
        )
        mocker.patch.object(discord_guild, "categories", [1, 2, 3])
        bot = build_bot(mock_games=True, create_connection=False)
        async with TasksAction.create(bot) as action:
            await action.cleanup_old_voice_channels()
        assert "looking in category" not in caplog.text

    async def test_when_voice_channel_in_grace_period(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc),
        )
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()
        assert "channel is in grace period" in caplog.text

    async def test_when_voice_channel_is_occupied(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: True  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()
        assert "channel is occupied" in caplog.text

    async def test_when_voice_channel_is_without_permissions(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions()
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()
        assert f"no permissions to delete channel ({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_renamed(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"XXX-Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(hours=1),
        )
        game.voice_xid = voice_channel.id  # type: ignore
        DatabaseSession.commit()
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()
        assert f"deleting channel {voice_channel.name}({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_not_for_game(
        self,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"XXX-Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(hours=1),
        )
        game.voice_xid = voice_channel.id + 1  # type: ignore
        DatabaseSession.commit()
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()

    async def test_when_voice_channel_is_occupied_and_old(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(days=1),
        )
        voice_channel.voice_states.keys = lambda: True  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_deleted(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
    ) -> None:
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_deleted_and_batched(
        self,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
        mocker: MockerFixture,
    ) -> None:
        import spellbot.actions.tasks_action as mod

        mocker.patch.object(mod.settings, "VOICE_CLEANUP_BATCH", 0)
        manage_perms = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=pytz.utc) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text
        assert "batch limit reached" in caplog.text
