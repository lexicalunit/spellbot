from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot import __version__
from spellbot.cogs import AboutCog
from tests.mixins import InteractionMixin

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestCogAbout(InteractionMixin):
    async def test_about(self, freezer: FrozenDateTimeFactory) -> None:
        freezer.move_to("2021-03-01")

        cog = AboutCog(self.bot)
        await self.run(cog.about)

        self.interaction.response.send_message.assert_called_once()  # type: ignore
        assert self.interaction.response.send_message.call_args_list[0].kwargs[  # type: ignore
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
            "thumbnail": {"url": self.settings.thumb(None)},
            "title": "SpellBot",
            "type": "rich",
            "url": "http://spellbot.io/",
            "flags": 0,
        }
