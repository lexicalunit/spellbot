from __future__ import annotations

import pytest
from spellbot import __version__
from spellbot.cogs import AboutCog

from tests.mixins import InteractionMixin


@pytest.mark.asyncio()
class TestCogAbout(InteractionMixin):
    async def test_about(self) -> None:
        cog = AboutCog(self.bot)
        await self.run(cog.about)

        self.interaction.response.send_message.assert_called_once()
        assert self.interaction.response.send_message.call_args_list[0].kwargs[
            "embed"
        ].to_dict() == {
            "color": self.settings.INFO_EMBED_COLOR,
            "description": (
                "_The Discord bot for [SpellTable](https://spelltable.wizards.com/)._\n"
                "\n"
                "Having issues with SpellBot? Please [report bugs]"
                "(https://github.com/lexicalunit/spellbot/issues)!\n"
                "\n"
                f"[🔗 Add SpellBot to your Discord!]({self.settings.BOT_INVITE_LINK})\n"
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
            "thumbnail": {"url": self.settings.THUMB_URL},
            "title": "SpellBot",
            "type": "rich",
            "url": "http://spellbot.io/",
        }
