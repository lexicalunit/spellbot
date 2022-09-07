import logging

import discord
from ddtrace import tracer
from discord import Color, Embed, app_commands
from discord.ext import commands

from .. import SpellBot, __version__
from ..metrics import add_span_context
from ..operations import safe_send_channel
from ..settings import Settings
from ..utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)

ISSUES = "https://github.com/lexicalunit/spellbot/issues"
PATREON = "https://www.patreon.com/lexicalunit"


@for_all_callbacks(app_commands.check(is_guild))
class AboutCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @app_commands.command(name="about", description="Get information about SpellBot.")
    @tracer.wrap(name="interaction", resource="about")
    async def about(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        settings = Settings(interaction.guild_id)
        embed = Embed(title="SpellBot")
        embed.set_thumbnail(url=settings.THUMB_URL)
        version = f"[{__version__}](https://pypi.org/project/spellbot/{__version__}/)"
        embed.add_field(name="Version", value=version)
        author = "[@lexicalunit](https://github.com/lexicalunit)"
        embed.add_field(name="Author", value=author)
        embed.description = (
            "_The Discord bot for [SpellTable](https://spelltable.wizards.com/)._\n"
            "\n"
            f"Having issues with SpellBot? Please [report bugs]({ISSUES})!\n"
            "\n"
            f"[🔗 Add SpellBot to your Discord!]({settings.BOT_INVITE_LINK})\n"
            "\n"
            f"💜 Help keep SpellBot running by [becoming a patron!]({PATREON})"
        )
        embed.url = "http://spellbot.io/"
        embed.color = Color(settings.EMBED_COLOR)
        await safe_send_channel(interaction, embed=embed)


async def setup(bot: SpellBot):  # pragma: no cover
    await bot.add_cog(AboutCog(bot), guild=bot.settings.GUILD_OBJECT)
