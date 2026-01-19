from __future__ import annotations

import logging

import discord
from ddtrace.trace import tracer
from discord import Color, Embed, app_commands
from discord.ext import commands

from spellbot import SpellBot, __version__
from spellbot.metrics import add_span_context
from spellbot.operations import safe_send_channel
from spellbot.settings import settings
from spellbot.utils import for_all_callbacks, is_guild

logger = logging.getLogger(__name__)

ISSUES = "https://github.com/lexicalunit/spellbot/issues"
PATREON = "https://www.patreon.com/lexicalunit"


@for_all_callbacks(app_commands.check(is_guild))
class AboutCog(commands.Cog):
    def __init__(self, bot: SpellBot) -> None:
        self.bot = bot

    @app_commands.command(name="about", description="Get information about SpellBot.")
    @tracer.wrap(name="interaction", resource="about")
    async def about(self, interaction: discord.Interaction) -> None:
        add_span_context(interaction)
        embed = Embed(title="SpellBot")
        embed.set_thumbnail(url=settings.thumb(interaction.guild_id))
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
            "SpellBot's continued operation is made possible"
            " by [PlayEDH](https://www.playedh.com/) and my Patreon supporters.\n"
            "\n"
            f"💜 Help keep SpellBot running by [becoming a patron!]({PATREON})"
        )
        embed.url = "http://spellbot.io/"
        embed.color = Color(settings.INFO_EMBED_COLOR)
        await safe_send_channel(interaction, embed=embed)


async def setup(bot: SpellBot) -> None:  # pragma: no cover
    await bot.add_cog(AboutCog(bot), guild=settings.GUILD_OBJECT)
