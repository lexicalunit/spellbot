import logging

from ddtrace import tracer
from discord.ext import commands
from discord_slash import cog_ext
from discord_slash.context import MenuContext
from discord_slash.model import ContextMenuType

from .. import SpellBot
from ..interactions import BlockInteraction
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class BlockCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_context_menu(target=ContextMenuType.USER, name="Block")
    @tracer.wrap()
    async def block(self, ctx: MenuContext):
        assert ctx.target_author
        async with BlockInteraction.create(self.bot, ctx) as interaction:
            await interaction.block(target=ctx.target_author)

    @cog_ext.cog_context_menu(target=ContextMenuType.USER, name="Unblock")
    @tracer.wrap()
    async def unblock(self, ctx: MenuContext):
        assert ctx.target_author
        async with BlockInteraction.create(self.bot, ctx) as interaction:
            await interaction.unblock(target=ctx.target_author)


def setup(bot: SpellBot):
    bot.add_cog(BlockCog(bot))
