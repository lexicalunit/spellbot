import logging
from typing import Optional

from ddtrace import tracer
from discord.ext import commands

from .. import SpellBot
from ..interactions import BanInteraction
from ..metrics import add_span_context

logger = logging.getLogger(__name__)


class BanCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @commands.command(name="ban")
    @commands.check(commands.is_owner())
    @tracer.wrap(name="interaction", resource="ban")
    async def ban(self, ctx: commands.Context, arg: Optional[str] = None):
        add_span_context(ctx)
        async with BanInteraction.create(self.bot) as interaction:
            await interaction.set_banned(True, ctx, arg)

    @commands.command(name="unban")
    @commands.check(commands.is_owner())
    @tracer.wrap(name="interaction", resource="unban")
    async def unban(self, ctx: commands.Context, arg: Optional[str] = None):
        add_span_context(ctx)
        async with BanInteraction.create(self.bot) as interaction:
            await interaction.set_banned(False, ctx, arg)


def setup(bot: SpellBot):
    bot.add_cog(BanCog(bot))
