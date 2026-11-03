# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from spellbot.actions import LookingForGameAction
from spellbot.cogs.choices import BRACKET_CHOICES, FORMAT_CHOICES, SERVICE_CHOICES
from spellbot.operations import safe_defer_interaction
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_admin, is_guild, traced_interaction

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
    @app_commands.choices(format=FORMAT_CHOICES)
    @app_commands.describe(bracket="What commander bracket do you want to play?")
    @app_commands.choices(bracket=BRACKET_CHOICES)
    @app_commands.describe(service="What service do you want to use to play this game?")
    @app_commands.choices(service=SERVICE_CHOICES)
    @traced_interaction()
    async def game(
        self,
        interaction: discord.Interaction,
        players: str,
        format: int | None = None,
        bracket: int | None = None,
        service: int | None = None,
    ) -> None:
        assert interaction.channel_id is not None
        if not await safe_defer_interaction(interaction):  # pragma: no cover
            return
        async with LookingForGameAction.create(self.bot, interaction) as action:
            await action.create_game(players, format, bracket, service)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(EventsCog(bot), guild=settings.GUILD_OBJECT)
