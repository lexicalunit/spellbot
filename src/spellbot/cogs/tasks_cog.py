import logging
import sys
from os import getenv

from discord.ext import commands, tasks

from .. import SpellBot
from ..interactions import TaskInteraction
from ..settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


class TasksCog(commands.Cog):  # pragma: no cover
    def __init__(self, bot: SpellBot):
        self.bot = bot
        if not getenv("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules:
            self.cleanup_old_voice_channels.start()
            self.expire_inactive_games.start()

    @tasks.loop(minutes=settings.VOICE_CLEANUP_LOOP_M)
    async def cleanup_old_voice_channels(self):
        async with TaskInteraction.create(self.bot) as interaction:
            await interaction.cleanup_old_voice_channels()

    @cleanup_old_voice_channels.before_loop
    async def before_cleanup_old_voice_channels(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=settings.EXPIRE_GAMES_LOOP_M)
    async def expire_inactive_games(self):
        async with TaskInteraction.create(self.bot) as interaction:
            await interaction.expire_inactive_games()

    @expire_inactive_games.before_loop
    async def before_expire_inactive_games(self):
        await self.bot.wait_until_ready()


def setup(bot: SpellBot):
    bot.add_cog(TasksCog(bot))
