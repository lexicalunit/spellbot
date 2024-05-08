import logging

from ddtrace import tracer
from discord.ext import commands

from spellbot import SpellBot
from spellbot.actions.base_action import handle_exception
from spellbot.metrics import add_span_context
from spellbot.operations import safe_send_user
from spellbot.settings import settings
from spellbot.utils import load_extensions

logger = logging.getLogger(__name__)


class SyncCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    @tracer.wrap(name="interaction", resource="sync")
    async def sync(self, ctx: commands.Context[SpellBot]) -> None:
        add_span_context(self.bot)
        try:
            await load_extensions(self.bot, do_sync=True)
            await safe_send_user(ctx.message.author, "Commands synced!")
        except Exception as ex:
            try:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
            except Exception:  # pragma: no cover
                logger.exception("Failed to send error message to user.")
            await handle_exception(ex)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(SyncCog(bot), guild=settings.GUILD_OBJECT)
