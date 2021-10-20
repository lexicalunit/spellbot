import logging

from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.context import MenuContext
from discord_slash.model import ContextMenuType

from spellbot.client import SpellBot
from spellbot.interactions.score_interaction import ScoreInteraction
from spellbot.utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class ScoreCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_context_menu(target=ContextMenuType.USER, name="View Score")
    async def view_score(self, ctx: MenuContext):
        assert ctx.target_author
        async with ScoreInteraction.create(self.bot, ctx) as interaction:
            await interaction.execute(target=ctx.target_author)

    @cog_ext.cog_slash(name="score", description="View your game record on this server.")
    async def score(self, ctx: SlashContext):
        async with ScoreInteraction.create(self.bot, ctx) as interaction:
            await interaction.execute(target=ctx.author)

    @cog_ext.cog_slash(
        name="history",
        description="View historical game records in this channel.",
    )
    async def history(self, ctx: SlashContext):
        async with ScoreInteraction.create(self.bot, ctx) as interaction:
            await interaction.history()


def setup(bot: SpellBot):
    bot.add_cog(ScoreCog(bot))
