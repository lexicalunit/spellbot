import logging

from ddtrace import tracer
from discord.ext import commands, tasks

from .. import SpellBot
from ..actions import TasksAction
from ..environment import running_in_pytest
from ..settings import Settings

logger = logging.getLogger(__name__)
settings = Settings()


class TasksCog(commands.Cog):  # pragma: no cover
    def __init__(self, bot: SpellBot):
        self.bot = bot
        if not running_in_pytest():
            self.cleanup_old_voice_channels.start()  # pylint: disable=no-member
            self.expire_inactive_games.start()  # pylint: disable=no-member

    @tasks.loop(minutes=settings.VOICE_CLEANUP_LOOP_M)
    async def cleanup_old_voice_channels(self):
        with tracer.trace(name="command", resource="cleanup_old_voice_channels"):
            async with TasksAction.create(self.bot) as interaction:
                await interaction.cleanup_old_voice_channels()

    @cleanup_old_voice_channels.before_loop
    async def before_cleanup_old_voice_channels(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=settings.EXPIRE_GAMES_LOOP_M)
    async def expire_inactive_games(self):
        with tracer.trace(name="command", resource="expire_inactive_games"):
            async with TasksAction.create(self.bot) as interaction:
                await interaction.expire_inactive_games()

    @expire_inactive_games.before_loop
    async def before_expire_inactive_games(self):
        await self.bot.wait_until_ready()


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(TasksCog(bot), guild=bot.settings.GUILD_OBJECT)
