import logging
from typing import Optional

import discord
from ddtrace import tracer
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from .. import SpellBot
from ..actions.lfg_action import LookingForGameAction
from ..metrics import add_span_context
from ..models import GameFormat
from ..utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_guild))
class LookingForGameCog(commands.Cog):
    def __init__(self, bot: SpellBot):
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
    @app_commands.describe(format="What game format do you want to play?")
    @app_commands.choices(
        format=[Choice(name=str(format), value=format.value) for format in GameFormat],
    )
    @tracer.wrap(name="interaction", resource="lfg")
    async def lfg(
        self,
        interaction: discord.Interaction,
        friends: Optional[str] = None,
        seats: Optional[int] = None,
        format: Optional[int] = None,
    ):
        assert interaction.channel_id is not None
        add_span_context(interaction)
        await interaction.response.defer()
        async with self.bot.channel_lock(interaction.channel_id):
            async with LookingForGameAction.create(self.bot, interaction) as action:
                await action.execute(friends=friends, seats=seats, format=format)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(LookingForGameCog(bot), guild=bot.settings.GUILD_OBJECT)
