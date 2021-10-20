import logging
import re
from datetime import datetime, timedelta

from dateutil import tz
from discord.channel import VoiceChannel

from spellbot.client import SpellBot
from spellbot.interactions import BaseInteraction
from spellbot.operations import bot_can_delete_channel, safe_delete_channel
from spellbot.services.games import GamesService
from spellbot.settings import Settings

settings = Settings()
logger = logging.getLogger(__name__)


class VoiceChannelFilterer:
    def __init__(self, games: GamesService):
        self.games = games
        grace_delta = timedelta(minutes=settings.VOICE_GRACE_PERIOD_M)
        grace_time_ago = datetime.utcnow() - grace_delta
        self.grace_time_ago = grace_time_ago.replace(tzinfo=tz.UTC)
        age_limit_delta = timedelta(hours=settings.VOICE_AGE_LIMIT_H)
        age_limit_ago = datetime.utcnow() - age_limit_delta
        self.age_limit_ago = age_limit_ago.replace(tzinfo=tz.UTC)

    async def filter(self, voice_channels: list[VoiceChannel]) -> list[VoiceChannel]:
        channels: list[VoiceChannel] = []

        for channel in voice_channels:
            logger.info("considering channel %s(%s)", channel.name, channel.id)
            occupied = bool(channel.voice_states.keys())
            channel_created_at = channel.created_at.replace(tzinfo=tz.UTC)

            if channel_created_at > self.grace_time_ago:
                logger.info("channel is in grace period")
                continue

            if occupied and channel_created_at > self.age_limit_ago:
                logger.info("channel is occupied")
                continue

            if not bot_can_delete_channel(channel):
                logger.info("no permissions to delete channel")
                continue

            if re.match(r"\AGame-SB\d+\Z", channel.name):
                logger.info("channel matches name format, adding to delete list")
                channels.append(channel)
                continue

            logger.info("looking for matching game in database")
            found = await self.games.select_by_voice_xid(channel.id)
            if found:
                logger.info("matching game found, adding to delete list")
                channels.append(channel)

        return channels


class TaskInteraction(BaseInteraction):
    def __init__(self, bot: SpellBot):
        super().__init__(bot)

    async def cleanup_old_voice_channels(self):
        logger.info("starting task cleanup_old_voice_channels")
        try:
            channels = await self.gather_channels()
            await self.delete_channels(channels)
        except BaseException as e:
            logger.exception("error: exception in background task: %s", e)

    async def gather_channels(self) -> list[VoiceChannel]:
        channels: list[VoiceChannel] = []
        active_guild_xids = set(g.id for g in self.bot.guilds)
        channel_filterer = VoiceChannelFilterer(self.services.games)

        for guild_xid in await self.services.guilds.voiced():
            await self.services.guilds.select(guild_xid)
            guild_name = await self.services.guilds.current_name()
            logger.info("looking in guild %s(%s)", guild_name, guild_xid)

            if guild_xid not in active_guild_xids:
                logger.warning("guild is not active")
                continue

            guild = self.bot.get_guild(guild_xid)
            if not guild:
                logger.info("could not get guild from discord.py cache")
                continue

            voice_categories = filter(
                lambda c: c.name.startswith(settings.VOICE_CATEGORY_PREFIX),
                guild.categories,
            )
            for category in voice_categories:
                logger.info("looking in category %s", category.name)
                voice_channels = await channel_filterer.filter(category.voice_channels)
                channels.extend(voice_channels)

        return channels

    async def delete_channels(self, channels: list[VoiceChannel]):
        batch = 0
        for channel in sorted(channels, key=lambda c: c.created_at):
            logger.info("deleting channel %s(%s)", channel.name, channel.id)
            await safe_delete_channel(channel, channel.guild.id)

            # Try to avoid rate limiting by the Discord API
            batch += 1
            if batch > settings.VOICE_CLEANUP_BATCH:
                remaining = len(channels) - settings.VOICE_CLEANUP_BATCH
                logger.info("batch limit reached, %s channels remain", remaining)
                break
