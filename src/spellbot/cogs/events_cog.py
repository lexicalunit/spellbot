from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from spellbot.actions import LookingForGameAction
from spellbot.enums import GAME_BRACKET_ORDER, GAME_FORMAT_ORDER, GAME_SERVICE_ORDER
from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_admin, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class EventsCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(name="game", description="Immediately create and start an ad-hoc game.")
    @app_commands.describe(players="You must mention ALL players for this game.")
    @app_commands.describe(format="What game format do you want to play?")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GAME_FORMAT_ORDER],
    )
    @app_commands.describe(format="What commander bracket do you want to play?")
    @app_commands.choices(
        bracket=[Choice(name=str(bracket), value=bracket.value) for bracket in GAME_BRACKET_ORDER],
    )
    @app_commands.describe(service="What service do you want to use to play this game?")
    @app_commands.choices(
        service=[Choice(name=str(service), value=service.value) for service in GAME_SERVICE_ORDER],
    )
    @tracer.wrap(name="interaction", resource="game")
    async def game(
        self,
        interaction: discord.Interaction,
        players: str,
        format: int | None = None,
        bracket: int | None = None,
        service: int | None = None,
    ) -> None:
        assert interaction.channel_id is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):
            return
        async with LookingForGameAction.create(self.bot, interaction) as action:
            await action.create_game(players, format, bracket, service)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(EventsCog(bot), guild=settings.GUILD_OBJECT)
