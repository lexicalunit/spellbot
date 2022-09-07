import logging
from typing import Optional

import discord
from ddtrace import tracer
from discord import app_commands
from discord.ext import commands

from .. import SpellBot
from ..actions import ScoreAction
from ..metrics import add_span_context
from ..utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class ScoreCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(
        name="score",
        description="View your or another user's play history on this server.",
    )
    @app_commands.describe(user="Mention another user to see their history instead of your own")
    @tracer.wrap(name="interaction", resource="score")
    async def score(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        add_span_context(interaction)
        async with ScoreAction.create(self.bot, interaction) as action:
            await action.execute(target=user or interaction.user)

    @app_commands.command(
        name="history",
        description="View historical game records in this channel.",
    )
    @tracer.wrap(name="interaction", resource="history")
    async def history(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with ScoreAction.create(self.bot, interaction) as action:
            await action.history()


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(ScoreCog(bot), guild=bot.settings.GUILD_OBJECT)
