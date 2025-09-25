from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from ddtrace.trace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from spellbot.actions.lfg_action import LookingForGameAction
from spellbot.enums import GAME_BRACKET_ORDER, GAME_FORMAT_ORDER, GAME_SERVICE_ORDER
from spellbot.metrics import add_span_context
from spellbot.operations import safe_defer_interaction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

if TYPE_CHECKING:
    from spellbot import SpellBot

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class LookingForGameCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(name="lfg", description="Looking for game.")
    @app_commands.describe(friends="Mention friends to join this game with.")
    @app_commands.describe(seats="How many players can be seated at this game?")
    @app_commands.choices(
        seats=[
            Choice(name="2", value=2),
            Choice(name="3", value=3),
            Choice(name="4", value=4),
        ],
    )
    @app_commands.describe(rules="Any additional rules or requests for this game.")
    @app_commands.describe(service="What service do you want to use to play this game?")
    @app_commands.choices(
        service=[Choice(name=str(service), value=service.value) for service in GAME_SERVICE_ORDER],
    )
    @app_commands.describe(format="What game format do you want to play?")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GAME_FORMAT_ORDER],
    )
    @app_commands.describe(bracket="What commander bracket do you want to play?")
    @app_commands.choices(
        bracket=[Choice(name=str(bracket), value=bracket.value) for bracket in GAME_BRACKET_ORDER],
    )
    @tracer.wrap(name="interaction", resource="lfg")
    async def lfg(
        self,
        interaction: discord.Interaction,
        friends: str | None = None,
        seats: int | None = None,
        rules: str | None = None,
        service: int | None = None,
        format: int | None = None,
        bracket: int | None = None,
    ) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):
            return
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LookingForGameAction.create(self.bot, interaction) as action,
        ):
            await action.execute(
                friends=friends,
                seats=seats,
                rules=rules,
                format=format,
                bracket=bracket,
                service=service,
            )

    @app_commands.command(name="rematch", description="Play another game with the last group.")
    @tracer.wrap(name="interaction", resource="rematch")
    async def rematch(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        add_span_context(interaction)
        if not await safe_defer_interaction(interaction):
            return
        async with (
            self.bot.guild_lock(interaction.guild.id),
            LookingForGameAction.create(self.bot, interaction) as action,
        ):
            await action.execute_rematch()


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(LookingForGameCog(bot), guild=settings.GUILD_OBJECT)
