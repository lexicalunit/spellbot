from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot import __version__
from spellbot.cogs import AboutCog
from tests.fixtures import get_last_send_message, run_command

if TYPE_CHECKING:
    import discord
    from freezegun.api import FrozenDateTimeFactory

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestCogAbout:
    async def test_about(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        settings: Settings,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to("2021-03-01")

        cog = AboutCog(bot)
        await run_command(cog.about, interaction)

        assert get_last_send_message(interaction, "embed") == {
            "color": settings.INFO_EMBED_COLOR,
            "description": (
                "_The Discord bot for Webcam Magic._\n"
                "\n"
                "Having issues with SpellBot? Please [report bugs]"
                "(https://github.com/lexicalunit/spellbot/issues)!\n"
                "\n"
                f"[🔗 Add SpellBot to your Discord!]({settings.BOT_INVITE_LINK})\n"
                "\n"
                "SpellBot's continued operation is made possible"
                " by [PlayEDH](https://www.playedh.com/) and my Patreon supporters.\n"
                "\n"
                "💜 Help keep SpellBot running by [becoming a patron!]"
                "(https://www.patreon.com/lexicalunit)"
            ),
            "fields": [
                {
                    "inline": True,
                    "name": "Version",
                    "value": (f"[{__version__}](https://pypi.org/project/spellbot/{__version__}/)"),
                },
                {
                    "inline": True,
                    "name": "Author",
                    "value": "[@lexicalunit](https://github.com/lexicalunit)",
                },
            ],
            "thumbnail": {"url": settings.thumb(None)},
            "title": "SpellBot",
            "type": "rich",
            "url": "http://spellbot.io/",
            "flags": 0,
        }
