from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot.actions import ScoreAction
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class ScoreCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="score",
        description="View your or another user's play history on this server.",
    )
    @app_commands.describe(user="Mention another user to see their history instead of your own")
    # @tracer.wrap(name="interaction", resource="score")
    # There's a bug when combining `@tracer.wrap`, `@app_commands.describe` and discord.User.
    # See: https://github.com/Rapptz/discord.py/issues/10317.
    async def score(
        self,
        interaction: discord.Interaction,
        user: discord.User | discord.Member | None = None,
    ) -> None:
        with tracer.trace("interaction", resource="score"):
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

    @app_commands.command(name="top", description="View the top players in this channel.")
    @app_commands.describe(monthly="Ranks for this month only?")
    @app_commands.describe(ago="How many months ago?")
    @tracer.wrap(name="interaction", resource="top")
    async def top(
        self,
        interaction: discord.Interaction,
        monthly: bool = True,
        ago: int = 0,
    ) -> None:
        add_span_context(interaction)
        async with ScoreAction.create(self.bot, interaction) as action:
            await action.top(monthly, ago)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(ScoreCog(bot), guild=settings.GUILD_OBJECT)
