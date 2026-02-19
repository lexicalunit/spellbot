from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot.actions import AnalyticsAction
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_admin, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class AnalyticsCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="analytics",
        description="View server analytics dashboard (admin only).",
    )
    @tracer.wrap(name="interaction", resource="analytics")
    async def analytics(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        async with AnalyticsAction.create(self.bot, interaction) as action:
            await action.execute()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(AnalyticsCog(bot), guild=settings.GUILD_OBJECT)
