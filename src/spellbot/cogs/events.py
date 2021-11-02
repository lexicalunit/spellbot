import logging
from typing import Optional

from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.model import SlashCommandOptionType

from spellbot.client import SpellBot
from spellbot.interactions.lfg_interaction import LookingForGameInteraction
from spellbot.models.game import GameFormat
from spellbot.utils import for_all_callbacks, is_admin

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.check(is_admin))
@for_all_callbacks(commands.guild_only())
class EventsCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="game",
        description="Immediately create and start an ad-hoc game.",
        options=[
            {
                "name": "players",
                "description": "Mention all players for this game.",
                "required": True,
                "type": SlashCommandOptionType.STRING.value,
            },
            {
                "name": "format",
                "description": "What game format? Default if unspecified is Commander.",
                "required": False,
                "type": SlashCommandOptionType.INTEGER.value,
                "choices": [
                    {
                        "name": str(format),
                        "value": format.value,
                    }
                    for format in GameFormat
                ],
            },
        ],
    )
    async def game(self, ctx: SlashContext, players: str, format: Optional[int] = None):
        async with LookingForGameInteraction.create(self.bot, ctx) as interaction:
            await interaction.create_game(players, format)


def setup(bot: SpellBot):
    bot.add_cog(EventsCog(bot))
