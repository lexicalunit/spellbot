import logging
import sys
from os import getenv

from discord.ext import commands, tasks

from spellbot.client import SpellBot
from spellbot.interactions.task_interaction import TaskInteraction
from spellbot.settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


class TasksCog(commands.Cog):  # pragma: no cover
    def __init__(self, bot: SpellBot):
        self.bot = bot
        if not getenv("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules:
            self.cleanup_old_voice_channels.start()

    @tasks.loop(minutes=settings.VOICE_CLEANUP_LOOP_M)
    async def cleanup_old_voice_channels(self):
        async with TaskInteraction.create(self.bot) as interaction:
            await interaction.cleanup_old_voice_channels()

    @cleanup_old_voice_channels.before_loop
    async def before_cleanup_old_voice_channels(self):
        await self.bot.wait_until_ready()


def setup(bot: SpellBot):
    bot.add_cog(TasksCog(bot))
