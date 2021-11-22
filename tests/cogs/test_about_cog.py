import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot, __version__
from spellbot.cogs.about_cog import AboutCog
from spellbot.settings import Settings


@pytest.mark.asyncio
class TestCogAbout:
    async def test_about(
        self,
        settings: Settings,
        bot: SpellBot,
        ctx: InteractionContext,
    ):
        cog = AboutCog(bot)
        await cog.about.invoke(ctx)

        ctx.send.assert_called_once()
        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_The Discord bot for [SpellTable](https://spelltable.wizards.com/)._\n"
                "\n"
                "Having issues with SpellBot? Please [report bugs]"
                "(https://github.com/lexicalunit/spellbot/issues)!\n"
                "\n"
                f"[🔗 Add SpellBot to your Discord!]({settings.BOT_INVITE_LINK})\n"
                "\n"
                "💜 Help keep SpellBot running by [becoming a patron!]"
                "(https://www.patreon.com/lexicalunit)"
            ),
            "fields": [
                {
                    "inline": True,
                    "name": "Version",
                    "value": (
                        f"[{__version__}]"
                        f"(https://pypi.org/project/spellbot/{__version__}/)"
                    ),
                },
                {
                    "inline": True,
                    "name": "Author",
                    "value": "[@lexicalunit](https://github.com/lexicalunit)",
                },
            ],
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "SpellBot",
            "type": "rich",
            "url": "http://spellbot.io/",
        }
