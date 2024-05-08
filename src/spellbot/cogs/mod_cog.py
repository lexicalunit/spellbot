import logging

import discord
from ddtrace import tracer
from discord import app_commands
from discord.ext import commands

from spellbot import SpellBot
from spellbot.actions import AdminAction
from spellbot.metrics import add_span_context
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild, is_mod

logger = logging.getLogger(__name__)


@for_all_callbacks(app_commands.check(is_mod))
@for_all_callbacks(app_commands.check(is_guild))
class ModCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    mod_group = app_commands.Group(name="mod", description="...")

    @mod_group.command(
        name="set_points",
        description="Set points for a player's record.",
    )
    @app_commands.describe(game_id="SpellBot ID of the game")
    @app_commands.describe(player="The player to set points for")
    @app_commands.describe(points="The points for the player")
    @tracer.wrap(name="interaction", resource="mod_set_points")
    async def mod_set_points(
        self,
        interaction: discord.Interaction,
        game_id: int,
        player: discord.User | discord.Member,
        points: int,
    ) -> None:
        add_span_context(interaction)
        async with AdminAction.create(self.bot, interaction) as action:
            await action.set_points(game_id, player.id, points)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(ModCog(bot), guild=settings.GUILD_OBJECT)
