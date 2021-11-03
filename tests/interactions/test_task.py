from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spellbot.client import SpellBot
from spellbot.database import DatabaseSession
from spellbot.interactions.task_interaction import TaskInteraction
from tests.factories.channel import ChannelFactory
from tests.factories.game import GameFactory
from tests.factories.guild import GuildFactory


@pytest.mark.asyncio
class TestInteractionTask:
    async def test_error_in_background_task(self, bot, monkeypatch, caplog):
        async with TaskInteraction.create(bot) as interaction:
            error = RuntimeError("gather-channels-error")
            gather_channels_mock = AsyncMock(retun_value=[])
            delete_channels_mock = AsyncMock(side_effect=error)
            monkeypatch.setattr(interaction, "gather_channels", gather_channels_mock)
            monkeypatch.setattr(interaction, "delete_channels", delete_channels_mock)
            await interaction.cleanup_old_voice_channels()
            assert "error: exception in background task" in caplog.text

    async def test_happy_path(self, bot, settings):
        db_guilds = GuildFactory.create_batch(5, voice_create=True)

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

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        for guild in bot.guilds:
            for category in guild.categories:
                for channel in category.voice_channels:
                    channel.delete.assert_called_once()

    async def test_channel_grace_period(self, bot, settings):
        db_guild = GuildFactory.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(minutes=1)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_channel_occupied(self, bot, settings):
        db_guild = GuildFactory.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {"foo": "bar"}
        voice_channel.created_at = datetime.utcnow() - timedelta(minutes=30)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_channel_occupied_past_limit(self, bot, settings):
        db_guild = GuildFactory.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {"foo": "bar"}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=3)
        voice_channel.delete = AsyncMock()

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_called_once()

    async def test_channel_with_bad_permissions(self, bot, settings):
        db_guild = GuildFactory.create(voice_create=True)

        bot_guilds = {}

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "Game-SB1"
        voice_channel.id = 1001
        voice_channel.voice_states = {}
        voice_channel.created_at = datetime.utcnow() - timedelta(days=1)
        voice_channel.delete = AsyncMock()
        del voice_channel.type

        category = MagicMock(spec=discord.CategoryChannel)
        category.name = settings.VOICE_CATEGORY_PREFIX
        category.voice_channels = [voice_channel]

        discord_guild = MagicMock(spec=discord.Guild)
        discord_guild.id = db_guild.xid
        discord_guild.name = db_guild.name
        discord_guild.categories = [category]

        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_channel_with_matching_message_id(self, bot, settings):
        db_guild = GuildFactory.create(voice_create=True)
        db_channel = ChannelFactory.create(guild=db_guild)
        db_game = GameFactory.create(guild=db_guild, channel=db_channel, voice_xid=123)

        DatabaseSession.expire_all()

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "BOGUS-CHANNEL-NAME"
        voice_channel.id = db_game.voice_xid
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

        bot_guilds = {}
        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_called_once()

    async def test_channel_without_matching_message_id(self, bot, settings):
        db_guild = GuildFactory.create(voice_create=True)
        db_channel = ChannelFactory.create(guild=db_guild)
        db_game = GameFactory.create(guild=db_guild, channel=db_channel, voice_xid=123)

        DatabaseSession.expire_all()

        voice_channel = MagicMock(spec=discord.VoiceChannel)
        voice_channel.name = "BOGUS-CHANNEL-NAME"
        voice_channel.id = db_game.voice_xid - 1
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

        bot_guilds = {}
        bot_guilds[discord_guild.id] = discord_guild

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        voice_channel.delete.assert_not_called()

    async def test_non_active_guilds(self, bot, settings):
        db_guilds = GuildFactory.create_batch(5, voice_create=True)

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

        class BotMock(SpellBot):
            guilds = []  # type: ignore
            get_guild = lambda self, id: bot_guilds.get(id)

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        for guild in bot_guilds.values():
            for category in guild.categories:
                for channel in category.voice_channels:
                    channel.delete.assert_not_called()

    async def test_when_guild_cache_failure(self, bot, settings):
        db_guilds = GuildFactory.create_batch(5, voice_create=True)

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

        class BotMock(SpellBot):
            guilds = list(bot_guilds.values())  # type: ignore
            get_guild = lambda self, id: None

        bot.__class__ = BotMock

        async with TaskInteraction.create(bot) as interaction:
            channels = await interaction.gather_channels()
            await interaction.delete_channels(channels)

        for guild in bot.guilds:
            for category in guild.categories:
                for channel in category.voice_channels:
                    channel.delete.assert_not_called()

    async def test_delete_channels_batching(self, bot, settings):
        channels = []
        for i in range(settings.VOICE_CLEANUP_BATCH * 2):
            channel = MagicMock(spec=discord.VoiceChannel)
            channel.name = f"Game-SB{i}"
            channel.id = 1000 + i
            channel.created_at = datetime.utcnow() - timedelta(days=1)
            channel.delete = AsyncMock()
            channels.append(channel)

        async with TaskInteraction.create(bot) as interaction:
            await interaction.delete_channels(channels)

        for i, channel in enumerate(channels):
            if i <= settings.VOICE_CLEANUP_BATCH:
                channel.delete.assert_called_once()
            else:
                channel.delete.assert_not_called()
