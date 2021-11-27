from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spellbot import SpellBot
from spellbot.database import DatabaseSession
from spellbot.interactions import TaskInteraction, task_interaction
from spellbot.models import Game, Guild
from spellbot.settings import Settings
from tests.fixtures import Factories
from tests.mixins import BaseMixin
from tests.mocks import (
    build_channel,
    build_client_user,
    build_message,
    mock_discord_guild,
    mock_operations,
)


def create_bot_guilds(settings, db_guilds: list[Guild]) -> dict:
    bot_guilds = {}
    for i, db_guild in enumerate(db_guilds):
        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = f"Game-SB{i}"
        voice_channel.id = 1000 + i
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=1)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild
    return bot_guilds


@pytest.mark.asyncio
class TestInteractionTask(BaseMixin):
    async def test_error_in_background_task(self, monkeypatch, caplog):
        async with TaskInteraction.create(self.bot) as interaction:
            error = RuntimeError("gather-channels-error")
            gather_channels_mock = AsyncMock(retun_value=[])
            delete_channels_mock = AsyncMock(side_effect=error)
            monkeypatch.setattr(interaction, "gather_channels", gather_channels_mock)
            monkeypatch.setattr(interaction, "delete_channels", delete_channels_mock)
            await interaction.cleanup_old_voice_channels()
            assert "error: exception in background task" in caplog.text


@pytest.mark.asyncio
class TestInteractionTaskExpireInactiveGames(BaseMixin):
    async def test_delete_none(self):
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        self.factories.game.create_batch(5, guild=guild, channel=channel)

        async with TaskInteraction.create(self.bot) as interaction:
            await interaction.expire_inactive_games()

        assert DatabaseSession.query(Game).count() == 5

    async def test_delete_all(
        self,
        bot: SpellBot,
        settings: Settings,
        factories: Factories,
    ):
        long_ago = datetime.utcnow() - timedelta(minutes=settings.EXPIRE_TIME_M + 1)
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        factories.game.create_batch(5, guild=guild, channel=channel, updated_at=long_ago)

        async with TaskInteraction.create(bot) as interaction:
            await interaction.expire_inactive_games()

        assert DatabaseSession.query(Game).filter(Game.deleted_at.is_(None)).count() == 0

    async def test_delete_happy_path(self):
        long_ago = datetime.utcnow() - timedelta(minutes=self.settings.EXPIRE_TIME_M + 1)
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        self.factories.game.create(guild=guild, channel=channel, updated_at=long_ago)

        async with TaskInteraction.create(self.bot) as interaction:
            with mock_operations(task_interaction):
                discord_guild = mock_discord_guild(guild)
                discord_channel = build_channel(discord_guild)
                client_user = build_client_user()
                discord_message = build_message(
                    discord_guild,
                    discord_channel,
                    client_user,
                )
                task_interaction.safe_fetch_text_channel = AsyncMock(
                    return_value=discord_channel,
                )
                task_interaction.safe_fetch_message = AsyncMock(
                    return_value=discord_message,
                )

                await interaction.expire_inactive_games()

                task_interaction.safe_update_embed.assert_called_once_with(
                    discord_message,
                    components=[],
                    content="Sorry, this game was expired due to inactivity.",
                    embed=None,
                )

        assert DatabaseSession.query(Game).filter(Game.deleted_at.is_(None)).count() == 0

    async def test_delete_when_fetch_channel_fails(
        self,
        bot: SpellBot,
        settings: Settings,
        factories: Factories,
    ):
        long_ago = datetime.utcnow() - timedelta(minutes=settings.EXPIRE_TIME_M + 1)
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        factories.game.create(guild=guild, channel=channel, updated_at=long_ago)

        async with TaskInteraction.create(bot) as interaction:
            with mock_operations(task_interaction):
                task_interaction.safe_fetch_text_channel = AsyncMock(return_value=None)

                await interaction.expire_inactive_games()

        assert DatabaseSession.query(Game).filter(Game.deleted_at.is_(None)).count() == 0

    async def test_delete_when_fetch_message_fails(self):
        long_ago = datetime.utcnow() - timedelta(minutes=self.settings.EXPIRE_TIME_M + 1)
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        self.factories.game.create(guild=guild, channel=channel, updated_at=long_ago)

        async with TaskInteraction.create(self.bot) as interaction:
            with mock_operations(task_interaction):
                discord_guild = mock_discord_guild(guild)
                discord_channel = build_channel(discord_guild)
                task_interaction.safe_fetch_text_channel = AsyncMock(
                    return_value=discord_channel,
                )
                task_interaction.safe_fetch_message = AsyncMock(return_value=None)

                await interaction.expire_inactive_games()

        assert DatabaseSession.query(Game).filter(Game.deleted_at.is_(None)).count() == 0

    async def test_delete_when_game_has_no_message_xid(self):
        long_ago = datetime.utcnow() - timedelta(minutes=self.settings.EXPIRE_TIME_M + 1)
        guild = self.factories.guild.create()
        channel = self.factories.channel.create(guild=guild)
        self.factories.game.create(
            guild=guild,
            channel=channel,
            updated_at=long_ago,
            message_xid=None,
        )

        async with TaskInteraction.create(self.bot) as interaction:
            with mock_operations(task_interaction):
                await interaction.expire_inactive_games()

        assert DatabaseSession.query(Game).filter(Game.deleted_at.is_(None)).count() == 0


@pytest.mark.asyncio
class TestInteractionTaskCleanupOldVoicChannels(BaseMixin):
    async def test_happy_path(self):
        db_guilds = self.factories.guild.create_batch(5, voice_create=True)
        bot_guilds = create_bot_guilds(self.settings, db_guilds)

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        for guild in self.bot.guilds:
            for category in guild.categories:
                for channel in category.voice_channels:
                    channel.delete.assert_called_once()

    async def test_channel_grace_period(self):
        db_guild = self.factories.guild.create(voice_create=True)
        bot_guilds = create_bot_guilds(self.settings, [db_guild])

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(minutes=1)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = self.settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_channel_occupied(self):
        db_guild = self.factories.guild.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {"foo": "bar"}
        voice_channel.created_at = datetime.utcnow() - timedelta(minutes=30)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = self.settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_channel_occupied_past_limit(self):
        db_guild = self.factories.guild.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {"foo": "bar"}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=3)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = self.settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_called_once()

    async def test_channel_with_bad_permissions(self):
        db_guild = self.factories.guild.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=1)
        voice_channel.delete = AsyncMock()
        del voice_channel.type

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = self.settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_channel_with_matching_message_id(self):
        db_guild = self.factories.guild.create(voice_create=True)
        db_channel = self.factories.channel.create(guild=db_guild)
        db_game = self.factories.game.create(
            guild=db_guild,
            channel=db_channel,
            voice_xid=123,
        )

        DatabaseSession.expire_all()

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "BOGUS-CHANNEL-NAME"
        voice_channel.id = db_game.voice_xid
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=1)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = self.settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds = {}
        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_called_once()

    async def test_channel_without_matching_message_id(self):
        db_guild = self.factories.guild.create(voice_create=True)
        db_channel = self.factories.channel.create(guild=db_guild)
        db_game = self.factories.game.create(
            guild=db_guild,
            channel=db_channel,
            voice_xid=123,
        )

        DatabaseSession.expire_all()

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "BOGUS-CHANNEL-NAME"
        voice_channel.id = db_game.voice_xid - 1
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=1)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = self.settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds = {}
        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_non_active_guilds(self):
        db_guilds = self.factories.guild.create_batch(5, voice_create=True)
        bot_guilds = create_bot_guilds(self.settings, db_guilds)

        class BotMock(SpellBot):
            guilds = []  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        for guild in bot_guilds.values():
            for category in guild.categories:
                for channel in category.voice_channels:
                    channel.delete.assert_not_called()

    async def test_when_guild_cache_failure(self):
        db_guilds = self.factories.guild.create_batch(5, voice_create=True)
        bot_guilds = create_bot_guilds(self.settings, db_guilds)

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: None

        self.bot.__class__ = BotMock

        async with TaskInteraction.create(self.bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        for guild in self.bot.guilds:
            for category in guild.categories:
                for channel in category.voice_channels:
                    channel.delete.assert_not_called()

    async def test_delete_channels_batching(self):
        channels = []
        for i in range(self.settings.VOICE_CLEANUP_BATCH * 2):
            channel = MagicMock(spec=discord.VoiceChannel)
            channel.name = f"Game-SB{i}"
            channel.id = 1000 + i
            channel.created_at = datetime.utcnow() - timedelta(days=1)
            channel.delete = AsyncMock()
            channels.append(channel)

        async with TaskInteraction.create(self.bot) as interaction:
            await interaction.delete_channels(channels)

        for i, channel in enumerate(channels):
            if i <= self.settings.VOICE_CLEANUP_BATCH:
                channel.delete.assert_called_once()
            else:
                channel.delete.assert_not_called()
