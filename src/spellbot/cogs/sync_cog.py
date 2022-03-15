import logging

from ddtrace import tracer
from discord.ext import commands

from .. import SpellBot
from ..actions.base_action import handle_exception
from ..metrics import add_span_context
from ..operations import safe_send_user
from ..utils import load_extensions

logger = logging.getLogger(__name__)


class SyncCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    @tracer.wrap(name="interaction", resource="sync")
    async def sync(self, ctx: commands.Context[SpellBot]):
        add_span_context(self.bot)
        try:
            await load_extensions(self.bot, do_sync=True)
            await safe_send_user(ctx.message.author, "Commands synced!")
        except Exception as ex:
            try:
                await safe_send_user(ctx.message.author, f"Error: {ex}")
            except Exception:  # pragma: no cover
                pass
            await handle_exception(ex)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(SyncCog(bot), guild=bot.settings.GUILD_OBJECT)
