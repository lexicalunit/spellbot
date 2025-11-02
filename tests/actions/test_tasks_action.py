from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import discord
import pytest
import pytest_asyncio
from sqlalchemy import update

from spellbot.actions import TasksAction
from spellbot.client import build_bot
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild
from spellbot.services import ChannelsService, GamesService, GuildsService, ServicesRegistry
from tests.mocks import mock_discord_object

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.models import Channel, Guild
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture(autouse=True)
async def use_log_level_info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)


@pytest_asyncio.fixture(autouse=True)
def use_mock_sleep(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("asyncio.sleep", new_callable=AsyncMock)


@pytest_asyncio.fixture
async def mock_services() -> MagicMock:
    services = MagicMock(spec=ServicesRegistry)
    services.games = MagicMock(spec=GamesService)
    services.channels = MagicMock(spec=ChannelsService)
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
        discord_guild.categories.append(category)
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


@pytest.mark.asyncio
class TestTaskExpireInactiveChannels:
    async def test_when_nothing_to_expire(
        self,
        action: TasksAction,
        mock_services: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        action.services = mock_services
        await action.expire_inactive_games()
        mock_services.games.delete_games.assert_not_called()
        assert "starting task expire_inactive_games" in caplog.text

    async def test_when_exception_raised(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(action, "expire_games", AsyncMock(side_effect=RuntimeError))
        await action.expire_inactive_games()
        assert "error: exception in background task" in caplog.text

    async def test_when_active_game_exists(
        self,
        action: TasksAction,
        factories: Factories,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)
        factories.user.create(game=game)

        await action.expire_inactive_games()

        DatabaseSession.expire_all()
        assert game.deleted_at is None

    async def test_when_empty_game_exists(
        self,
        action: TasksAction,
        factories: Factories,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)

        await action.expire_inactive_games()

        DatabaseSession.expire_all()
        assert game.deleted_at is not None

    async def test_when_inactive_game_exists(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(
            guild=guild,
            channel=channel,
            updated_at=datetime.now(tz=UTC) - timedelta(days=1),
        )

        await action.expire_inactive_games()

        DatabaseSession.expire_all()
        assert game.deleted_at is not None
        assert f"expiring game {game.id}..." in caplog.text

    @pytest.mark.parametrize(
        "message_xid",
        [
            pytest.param(1234, id="message"),
            pytest.param(None, id="no_message"),
        ],
    )
    @pytest.mark.parametrize(
        "chan",
        [
            pytest.param("mock_channel", id="channel"),
            pytest.param(None, id="no_channel"),
        ],
    )
    @pytest.mark.parametrize(
        "post",
        [
            pytest.param("mock_post", id="post"),
            pytest.param(None, id="no_post"),
        ],
    )
    @pytest.mark.parametrize(
        "delete_expired",
        [
            pytest.param(True, id="delete"),
            pytest.param(False, id="update"),
        ],
    )
    async def test_when_inactive_game_with_players_exists(
        self,
        action: TasksAction,
        mock_services: MagicMock,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
        mocker: MockerFixture,
        message_xid: int | None,
        chan: Any,
        post: Any,
        delete_expired: bool,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(
            guild=guild,
            channel=channel,
            updated_at=datetime.now(tz=UTC) - timedelta(days=1),
        )
        if message_xid is not None:
            factories.post.create(guild=guild, channel=channel, game=game, message_xid=message_xid)
        factories.user.create(game=game)
        action.services = mock_services
        action.services.games.inactive_games = AsyncMock(return_value=[game.to_dict()])
        action.services.games.delete_games = AsyncMock()
        action.services.channels.select = AsyncMock(return_value={"delete_expired": delete_expired})
        mock_fetch_channel = AsyncMock(return_value=chan)
        mocker.patch("spellbot.actions.tasks_action.safe_fetch_text_channel", mock_fetch_channel)
        mock_get_partial = MagicMock(return_value=post)
        mocker.patch("spellbot.actions.tasks_action.safe_get_partial_message", mock_get_partial)
        mock_delete_message = AsyncMock()
        mocker.patch("spellbot.actions.tasks_action.safe_delete_message", mock_delete_message)
        mock_update_embed = AsyncMock()
        mocker.patch("spellbot.actions.tasks_action.safe_update_embed", mock_update_embed)

        await action.expire_inactive_games()

        DatabaseSession.expire_all()
        action.services.games.delete_games.assert_called_once_with([game.id])
        assert f"expiring game {game.id}..." in caplog.text
        if message_xid is not None:
            mock_fetch_channel.assert_called_once_with(action.bot, guild.xid, channel.xid)
            if chan is not None:
                mock_get_partial.assert_called_once_with(chan, guild.xid, message_xid)
                if post is not None:
                    action.services.channels.select.assert_called_once_with(channel.xid)
                    if delete_expired:
                        mock_delete_message.assert_called_once_with(post)
                    else:
                        mock_update_embed.assert_called_once_with(
                            post,
                            content="Sorry, this game was expired due to inactivity.",
                            embed=None,
                            view=None,
                        )


@pytest.mark.asyncio
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
        assert "error: exception in background task" in caplog.text

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
            discord.Permissions.manage_channels.flag,
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC),
        )
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()  # type: ignore
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
            discord.Permissions.manage_channels.flag,
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: True  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()  # type: ignore
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
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_not_called()  # type: ignore
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
        manage_perms = discord.Permissions(discord.Permissions.manage_channels.flag)
        voice_channel = make_voice_channel(
            id=4001,
            name=f"XXX-Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        stmt = (
            update(Game)  # type: ignore
            .where(Game.id == game.id)
            .values(voice_xid=voice_channel.id)
        )
        DatabaseSession.execute(stmt)
        DatabaseSession.commit()
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()  # type: ignore
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
            discord.Permissions.manage_channels.flag,
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"XXX-Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
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

        voice_channel.delete.assert_not_called()  # type: ignore

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
            discord.Permissions.manage_channels.flag,
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(days=1),
        )
        voice_channel.voice_states.keys = lambda: True  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()  # type: ignore
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
            discord.Permissions.manage_channels.flag,
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()  # type: ignore
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
            discord.Permissions.manage_channels.flag,
        )
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        voice_channel.voice_states.keys = lambda: False  # type: ignore
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        voice_channel.delete.assert_called_once()  # type: ignore
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text
        assert "batch limit reached" in caplog.text
