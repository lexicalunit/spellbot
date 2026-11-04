# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import discord
import pytest
import pytest_asyncio
from decoy import Decoy, matchers
from sqlalchemy import update

from spellbot import client, services
from spellbot.actions import TasksAction, base_action, tasks_action
from spellbot.actions.base_action import handle_exception
from spellbot.client import build_bot
from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket
from spellbot.errors import SpellBotError
from spellbot.models import Channel, Game, Guild
from spellbot.services.games import game_to_data
from tests.mocks import create_mock_channel, decoys, mock_discord_object
from tests.mocks.decoys import ANY

if TYPE_CHECKING:
    from collections.abc import Callable

    from spellbot import SpellBot
    from tests.fixtures import Factories, Stub

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture(autouse=True)
async def use_log_level_info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)


@pytest.fixture(autouse=True)
def use_mock_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", decoys.async_returning(None))


@pytest_asyncio.fixture
async def action(bot: SpellBot) -> TasksAction:
    async with TasksAction.create(bot) as action:
        return action


@pytest_asyncio.fixture
async def guild(factories: Factories) -> Guild:
    return factories.guild.create(voice_create=True)


@pytest_asyncio.fixture
async def guild_categories() -> list[discord.CategoryChannel]:
    return []


@pytest_asyncio.fixture
async def discord_guild(
    guild: Guild,
    decoy: Decoy,
    guild_categories: list[discord.CategoryChannel],
) -> discord.Guild:
    discord_obj = decoys.guild(decoy)
    discord_obj.id = guild.xid
    decoy.when(discord_obj.categories).then_return(guild_categories)
    return discord_obj


@pytest_asyncio.fixture
async def channel(factories: Factories, guild: Guild) -> Channel:
    return factories.channel.create(guild=guild)


@pytest_asyncio.fixture
async def game(factories: Factories, guild: Guild, channel: Channel) -> Game:
    return factories.game.create(guild=guild, channel=channel)


@pytest_asyncio.fixture
async def make_voice_channel(
    decoy: Decoy,
    discord_guild: discord.Guild,
) -> Callable[..., discord.VoiceChannel]:
    def factory(
        id: int,
        name: str,
        perms: discord.Permissions,
        created_at: datetime,
        *,
        occupied: bool = False,
    ) -> discord.VoiceChannel:
        voice = decoy.mock(cls=discord.VoiceChannel)
        voice.id = id
        voice.name = name
        voice.guild = discord_guild
        decoy.when(voice.type).then_return(discord.ChannelType.voice)
        decoy.when(voice.permissions_for(matchers.Anything())).then_return(perms)
        decoy.when(voice.created_at).then_return(created_at)
        voice_states = {1: decoy.mock(cls=discord.VoiceState)} if occupied else {}
        decoy.when(voice.voice_states).then_return(voice_states)
        return voice

    return factory


@pytest_asyncio.fixture
async def make_category_channel(
    discord_guild: discord.Guild,
    guild_categories: list[discord.CategoryChannel],
    decoy: Decoy,
) -> Callable[..., discord.CategoryChannel]:
    def factory(
        id: int,
        name: str,
        perms: discord.Permissions,
        voice_channels: list[discord.VoiceChannel],
    ) -> discord.CategoryChannel:
        category = decoy.mock(cls=discord.CategoryChannel)
        category.id = id
        category.name = name
        category.guild = discord_guild
        decoy.when(category.type).then_return(discord.ChannelType.category)
        decoy.when(category.permissions_for(matchers.Anything())).then_return(perms)
        decoy.when(category.voice_channels).then_return(voice_channels)
        guild_categories.append(category)
        return category

    return factory


@pytest_asyncio.fixture
async def bot(
    discord_guild: discord.Guild,
    decoy: Decoy,
    stub: Stub,
    monkeypatch: pytest.MonkeyPatch,
) -> SpellBot:
    monkeypatch.setattr(client.SpellBot, "guilds", property(lambda _: [discord_guild]))
    bot = build_bot(mock_games=True, create_connection=False)
    get_guild_fake = stub(bot, "get_guild")
    decoy.when(get_guild_fake(discord_guild.id)).then_return(discord_guild)
    return bot


@pytest.mark.asyncio
class TestTaskExpireInactiveChannels:
    async def test_when_nothing_to_expire(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        mock_services_games_delete_games = stub(services.games, "delete_games")
        await action.expire_inactive_games()
        decoy.verify(
            await mock_services_games_delete_games(game_ids=ANY),
            times=0,
            ignore_extra_args=True,
        )
        assert "starting task expire_inactive_games" in caplog.text

    async def test_when_exception_raised(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        expire_games_fake = stub(tasks_action, "expire_games")
        decoy.when(await expire_games_fake(bot=ANY, games=ANY), ignore_extra_args=True).then_raise(
            RuntimeError()
        )
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
        refreshed = await DatabaseSession.get(Game, game.id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None

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
        refreshed = await DatabaseSession.get(Game, game.id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None
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
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
        message_xid: int | None,
        chan: Any,
        post: Any,
        delete_expired: bool,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
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
        mock_services_games_inactive_games = stub(services.games, "inactive_games")
        decoy.when(await mock_services_games_inactive_games(), ignore_extra_args=True).then_return(
            [await game_to_data(game)]
        )
        mock_services_games_delete_games = stub(services.games, "delete_games")
        # The game had a queued player to dequeue; an empty game's post is just deleted.
        decoy.when(await mock_services_games_delete_games([game.id])).then_return(1)

        mock_channel_data = create_mock_channel(
            xid=channel.xid,
            guild_xid=guild.xid,
            delete_expired=delete_expired,
        )
        mock_services_channels_select = stub(services.channels, "select")
        decoy.when(
            await mock_services_channels_select(xid=ANY),
            ignore_extra_args=True,
        ).then_return(mock_channel_data)
        mock_fetch_channel = stub(base_action, "safe_fetch_text_channel")
        decoy.when(
            await mock_fetch_channel(client=ANY, guild_xid=ANY, channel_xid=ANY),
            ignore_extra_args=True,
        ).then_return(chan)
        mock_get_partial = stub(base_action, "safe_get_partial_message")
        decoy.when(
            mock_get_partial(channel=ANY, guild_xid=ANY, message_xid=ANY),
            ignore_extra_args=True,
        ).then_return(post)
        mock_delete_message = stub(base_action, "safe_delete_message")
        mock_update_embed = stub(base_action, "safe_update_embed")

        await action.expire_inactive_games()

        DatabaseSession.expire_all()
        assert f"expiring game {game.id}..." in caplog.text
        if message_xid is not None:
            decoy.verify(await mock_fetch_channel(action.bot, guild.xid, channel.xid), times=1)
            if chan is not None:
                decoy.verify(mock_get_partial(chan, guild.xid, message_xid), times=1)
                if post is not None:
                    decoy.verify(await mock_services_channels_select(channel.xid), times=1)
                    if delete_expired:
                        decoy.verify(await mock_delete_message(post, own_message=True), times=1)
                    else:
                        decoy.verify(
                            await mock_update_embed(
                                post,
                                content="Sorry, this game was expired due to inactivity.",
                                embed=None,
                                view=None,
                            ),
                            times=1,
                        )


@pytest.mark.asyncio
class TestTaskCleanupOldVoiceChannels:
    async def test_when_nothing_exists(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        mock_services_guilds_voiced = stub(services.guilds, "voiced")
        await action.cleanup_old_voice_channels()
        decoy.verify(await mock_services_guilds_voiced(), times=1)
        assert "starting task cleanup_old_voice_channels" in caplog.text

    async def test_when_exception_raised(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        gather_channels_fake = stub(action, "gather_channels")
        decoy.when(await gather_channels_fake(), ignore_extra_args=True).then_raise(RuntimeError())
        await action.cleanup_old_voice_channels()
        assert "error: exception in background task" in caplog.text

    async def test_when_guild_is_not_active(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(voice_create=True)
        monkeypatch.setattr(client.SpellBot, "guilds", property(lambda _: []))
        bot = build_bot(mock_games=True, create_connection=False)
        async with TasksAction.create(bot) as action:
            await action.cleanup_old_voice_channels()
        assert "guild is not active" in caplog.text

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Guild, guild.xid)
        assert refreshed
        assert refreshed.active is False

    async def test_when_guild_is_not_cached(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        guild = factories.guild.create(voice_create=True)
        discord_guild = mock_discord_object(decoy, guild)
        monkeypatch.setattr(client.SpellBot, "guilds", property(lambda _: [discord_guild]))
        bot = build_bot(mock_games=True, create_connection=False)
        async with TasksAction.create(bot) as action:
            await action.cleanup_old_voice_channels()
        assert "could not get guild from discord.py cache" in caplog.text

    async def test_when_guild_has_no_categories(
        self,
        caplog: pytest.LogCaptureFixture,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        guild = factories.guild.create(voice_create=True)
        discord_guild = mock_discord_object(decoy, guild)
        monkeypatch.setattr(client.SpellBot, "guilds", property(lambda _: [discord_guild]))
        monkeypatch.setattr(discord_guild, "categories", [1, 2, 3])
        bot = build_bot(mock_games=True, create_connection=False)
        get_guild_fake = stub(bot, "get_guild")
        decoy.when(get_guild_fake(guild.xid)).then_return(discord_guild)
        async with TasksAction.create(bot) as action:
            await action.cleanup_old_voice_channels()
        assert "looking in category" not in caplog.text

    async def test_when_voice_channel_in_grace_period(
        self,
        decoy: Decoy,
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

        decoy.verify(await voice_channel.delete(), times=0, ignore_extra_args=True)
        assert "channel is in grace period" in caplog.text

    async def test_when_voice_channel_is_occupied(
        self,
        decoy: Decoy,
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
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
            occupied=True,
        )
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete(), times=0, ignore_extra_args=True)
        assert "channel is occupied" in caplog.text

    async def test_when_voice_channel_is_without_permissions(
        self,
        decoy: Decoy,
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
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete(), times=0, ignore_extra_args=True)
        assert f"no permissions to delete channel ({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_renamed(
        self,
        decoy: Decoy,
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
        stmt = update(Game).where(Game.id == game.id).values(voice_xid=voice_channel.id)
        await DatabaseSession.execute(stmt)
        await DatabaseSession.commit()
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete())
        assert f"deleting channel {voice_channel.name}({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_not_for_game(
        self,
        decoy: Decoy,
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
        game.voice_xid = voice_channel.id + 1
        await DatabaseSession.commit()
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete(), times=0, ignore_extra_args=True)

    async def test_when_voice_channel_is_occupied_and_old(
        self,
        decoy: Decoy,
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
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(days=1),
            occupied=True,
        )
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete())
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_deleted(
        self,
        decoy: Decoy,
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
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete())
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text

    async def test_when_voice_channel_is_deleted_and_batched(
        self,
        decoy: Decoy,
        caplog: pytest.LogCaptureFixture,
        game: Game,
        channel: Channel,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        make_category_channel: Callable[..., discord.CategoryChannel],
        action: TasksAction,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import spellbot.actions.tasks_action as mod  # allow_inline

        monkeypatch.setattr(mod.settings, "VOICE_CLEANUP_BATCH", 0)
        manage_perms = discord.Permissions(discord.Permissions.manage_channels.flag)
        voice_channel = make_voice_channel(
            id=4001,
            name=f"Game-SB{game.id}",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
        make_category_channel(
            id=3001,
            name=channel.voice_category,
            perms=manage_perms,
            voice_channels=[voice_channel],
        )

        await action.cleanup_old_voice_channels()

        decoy.verify(await voice_channel.delete())
        assert f"deleting channel Game-SB{game.id}({voice_channel.id})" in caplog.text
        assert "batch limit reached" in caplog.text


@pytest.mark.asyncio
class TestNotifyPendingGames:
    async def test_no_games_does_nothing(
        self,
        action: TasksAction,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        mock_services_games_games_pending_notification = stub(
            services.games,
            "games_pending_notification",
        )
        decoy.when(
            await mock_services_games_games_pending_notification(),
            ignore_extra_args=True,
        ).then_return([])
        mock_services_alerts_find_matching_user_xids = stub(
            services.alerts,
            "find_matching_user_xids",
        )
        stub(services.alerts, "mark_notified")
        mock_safe_send = stub(tasks_action, "safe_send_user")

        await action.notify_pending_games()

        decoy.verify(
            await mock_services_alerts_find_matching_user_xids(
                guild_xid=ANY,
                format=ANY,
                bracket=ANY,
                channel_xid=ANY,
            ),
            times=0,
            ignore_extra_args=True,
        )
        decoy.verify(await mock_safe_send(user=ANY), times=0, ignore_extra_args=True)

    async def test_notifies_matching_users_and_marks_game(
        self,
        action: TasksAction,
        factories: Factories,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)
        game_data = await game_to_data(game)
        mock_services_games_games_pending_notification = stub(
            services.games,
            "games_pending_notification",
        )
        decoy.when(
            await mock_services_games_games_pending_notification(),
            ignore_extra_args=True,
        ).then_return([game_data])
        mock_services_alerts_find_matching_user_xids = stub(
            services.alerts,
            "find_matching_user_xids",
        )
        decoy.when(
            await mock_services_alerts_find_matching_user_xids(
                guild_xid=ANY,
                format=ANY,
                bracket=ANY,
                channel_xid=ANY,
            ),
            ignore_extra_args=True,
        ).then_return([101, 202])
        mock_services_alerts_mark_notified = stub(services.alerts, "mark_notified")
        fake_user = decoy.mock(cls=discord.User)
        mock_fetch_user = stub(tasks_action, "safe_fetch_user")
        decoy.when(
            await mock_fetch_user(client=ANY, user_xid=ANY),
            ignore_extra_args=True,
        ).then_return(fake_user)
        mock_safe_send = stub(tasks_action, "safe_send_user")

        await action.notify_pending_games()

        decoy.verify(
            await mock_safe_send(fake_user, kind="notification"),
            times=2,
            ignore_extra_args=True,
        )
        decoy.verify(await mock_services_alerts_mark_notified(game.id), times=1)

    async def test_skips_users_that_cannot_be_fetched(
        self,
        action: TasksAction,
        factories: Factories,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)
        game_data = await game_to_data(game)
        mock_services_games_games_pending_notification = stub(
            services.games,
            "games_pending_notification",
        )
        decoy.when(
            await mock_services_games_games_pending_notification(),
            ignore_extra_args=True,
        ).then_return([game_data])
        mock_services_alerts_find_matching_user_xids = stub(
            services.alerts,
            "find_matching_user_xids",
        )
        decoy.when(
            await mock_services_alerts_find_matching_user_xids(
                guild_xid=ANY,
                format=ANY,
                bracket=ANY,
                channel_xid=ANY,
            ),
            ignore_extra_args=True,
        ).then_return([101])
        mock_services_alerts_mark_notified = stub(services.alerts, "mark_notified")
        mock_fetch_user = stub(tasks_action, "safe_fetch_user")
        decoy.when(
            await mock_fetch_user(client=ANY, user_xid=ANY),
            ignore_extra_args=True,
        ).then_return(None)
        mock_safe_send = stub(tasks_action, "safe_send_user")

        await action.notify_pending_games()

        decoy.verify(await mock_safe_send(user=ANY), times=0, ignore_extra_args=True)
        decoy.verify(await mock_services_alerts_mark_notified(game.id), times=1)

    async def test_marks_notified_even_when_no_matches(
        self,
        action: TasksAction,
        factories: Factories,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)
        game_data = await game_to_data(game)
        mock_services_games_games_pending_notification = stub(
            services.games,
            "games_pending_notification",
        )
        decoy.when(
            await mock_services_games_games_pending_notification(),
            ignore_extra_args=True,
        ).then_return([game_data])
        mock_services_alerts_find_matching_user_xids = stub(
            services.alerts,
            "find_matching_user_xids",
        )
        decoy.when(
            await mock_services_alerts_find_matching_user_xids(
                guild_xid=ANY,
                format=ANY,
                bracket=ANY,
                channel_xid=ANY,
            ),
            ignore_extra_args=True,
        ).then_return([])
        mock_services_alerts_mark_notified = stub(services.alerts, "mark_notified")
        mock_safe_send = stub(tasks_action, "safe_send_user")

        await action.notify_pending_games()

        decoy.verify(await mock_safe_send(user=ANY), times=0, ignore_extra_args=True)
        decoy.verify(await mock_services_alerts_mark_notified(game.id), times=1)

    async def test_swallows_exceptions(
        self,
        action: TasksAction,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        mock_services_games_games_pending_notification = stub(
            services.games,
            "games_pending_notification",
        )
        decoy.when(
            await mock_services_games_games_pending_notification(),
            ignore_extra_args=True,
        ).then_raise(RuntimeError("boom"))

        await action.notify_pending_games()

        assert "error: exception in background task" in caplog.text

    async def test_embed_includes_bracket_and_jump_link(
        self,
        action: TasksAction,
        factories: Factories,
    ) -> None:

        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(
            guild=guild,
            channel=channel,
            bracket=GameBracket.BRACKET_3.value,
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=99999)
        game_data = await game_to_data(game)

        embed = action.build_notification_embed(game_data)

        assert embed.description is not None
        assert "Bracket:" in embed.description
        assert "Jump to the game post" in embed.description

    async def test_embed_omits_bracket_and_jump_link_when_absent(
        self,
        action: TasksAction,
        factories: Factories,
    ) -> None:
        guild: Guild = factories.guild.create()
        channel: Channel = factories.channel.create(guild=guild)
        game: Game = factories.game.create(guild=guild, channel=channel)
        game_data = await game_to_data(game)
        assert game_data.bracket == GameBracket.NONE.value

        embed = action.build_notification_embed(game_data)

        assert embed.description is not None
        assert "Bracket:" not in embed.description
        assert "Jump to the game post" not in embed.description


@pytest.mark.asyncio
class TestPatreonSync:
    async def test_patreon_sync(
        self,
        action: TasksAction,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        mock_supporters = stub(services.patreon, "supporters")
        decoy.when(await mock_supporters(), ignore_extra_args=True).then_return({123, 456, 789})

        await action.patreon_sync()

        assert action.bot.supporters == {123, 456, 789}


@pytest.mark.asyncio
class TestHandleException:
    async def test_reraises_spellbot_error(self) -> None:

        class TestSpellBotError(SpellBotError):
            pass

        error = TestSpellBotError("test error")
        with pytest.raises(TestSpellBotError):
            await handle_exception(error)

    async def test_rolls_back_and_reraises_other_exceptions(
        self,
        decoy: Decoy,
        stub: Stub,
    ) -> None:

        mock_rollback = stub(base_action.DatabaseSession, "rollback")

        error = RuntimeError("unexpected error")
        with pytest.raises(RuntimeError):
            await handle_exception(error)

        decoy.verify(await mock_rollback(), times=1, ignore_extra_args=True)
