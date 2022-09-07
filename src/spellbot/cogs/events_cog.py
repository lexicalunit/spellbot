import logging
from typing import Optional

import discord
from ddtrace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from .. import SpellBot
from ..actions import LookingForGameAction
from ..metrics import add_span_context
from ..models import GameFormat
from ..utils import for_all_callbacks, is_admin, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_admin))
@for_all_callbacks(app_commands.check(is_guild))
class EventsCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(name="game", description="Immediately create and start an ad-hoc game.")
    @app_commands.describe(players="Mention all players for this game.")
    @app_commands.describe(format="What game format? Default if unspecified is Commander.")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GameFormat],
    )
    @tracer.wrap(name="interaction", resource="game")
    async def game(
        self,
        interaction: discord.Interaction,
        players: str,
        format: Optional[int] = None,
    ) -> None:
        assert interaction.channel_id is not None
        add_span_context(interaction)
        await interaction.response.defer()
        async with LookingForGameAction.create(self.bot, interaction) as action:
            await action.create_game(players, format)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(EventsCog(bot), guild=bot.settings.GUILD_OBJECT)
