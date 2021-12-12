import logging

from ddtrace import tracer
from discord import Color, Embed
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from .. import SpellBot, __version__
from ..operations import safe_send_channel
from ..settings import Settings
from ..utils import for_all_callbacks

logger = logging.getLogger(__name__)


@for_all_callbacks(commands.guild_only())
class AboutCog(commands.Cog):
    def __init__(self, bot: SpellBot):
        self.bot = bot

    @cog_ext.cog_slash(name="about", description="Get information about SpellBot.")
    @tracer.wrap(name="command", resource="about")
    async def about(self, ctx: SlashContext):
        settings = Settings()
        embed = Embed(title="SpellBot")
        embed.set_thumbnail(url=settings.THUMB_URL)
        version = f"[{__version__}](https://pypi.org/project/spellbot/{__version__}/)"
        embed.add_field(name="Version", value=version)
        author = "[@lexicalunit](https://github.com/lexicalunit)"
        embed.add_field(name="Author", value=author)
        embed.description = (
            "_The Discord bot for [SpellTable](https://spelltable.wizards.com/)._\n"
            "\n"
            "Having issues with SpellBot? "
            "Please [report bugs](https://github.com/lexicalunit/spellbot/issues)!\n"
            "\n"
            f"[🔗 Add SpellBot to your Discord!]({settings.BOT_INVITE_LINK})\n"
            "\n"
            "💜 Help keep SpellBot running by "
            "[becoming a patron!](https://www.patreon.com/lexicalunit)"
        )
        embed.url = "http://spellbot.io/"
        embed.color = Color(settings.EMBED_COLOR)
        await safe_send_channel(ctx, embed=embed)


def setup(bot: SpellBot):
    bot.add_cog(AboutCog(bot))
