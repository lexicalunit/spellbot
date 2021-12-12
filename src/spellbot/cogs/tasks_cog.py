import logging

from ddtrace import tracer
from discord.ext import commands, tasks

from .. import SpellBot
from ..environment import running_in_pytest
from ..interactions import TaskInteraction
from ..settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


class TasksCog(commands.Cog):  # pragma: no cover
    def __init__(self, bot: SpellBot):
        self.bot = bot
        if not running_in_pytest():
            self.cleanup_old_voice_channels.start()
            self.expire_inactive_games.start()

    @tasks.loop(minutes=settings.VOICE_CLEANUP_LOOP_M)
    async def cleanup_old_voice_channels(self):
        with tracer.trace(name="spellbot.cogs.task_cog.cleanup_old_voice_channels"):
            async with TaskInteraction.create(self.bot) as interaction:
                await interaction.cleanup_old_voice_channels()

    @cleanup_old_voice_channels.before_loop
    async def before_cleanup_old_voice_channels(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=settings.EXPIRE_GAMES_LOOP_M)
    async def expire_inactive_games(self):
        with tracer.trace(name="spellbot.cogs.task_cog.expire_inactive_games"):
            async with TaskInteraction.create(self.bot) as interaction:
                await interaction.expire_inactive_games()

    @expire_inactive_games.before_loop
    async def before_expire_inactive_games(self):
        await self.bot.wait_until_ready()


def setup(bot: SpellBot):
    bot.add_cog(TasksCog(bot))
