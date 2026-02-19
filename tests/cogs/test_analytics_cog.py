from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest

from spellbot.cogs import AnalyticsCog
from tests.fixtures import get_last_send_message, run_command

if TYPE_CHECKING:
    import discord

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestCogAnalytics:
    async def test_analytics(
        self,
        bot: SpellBot,
        interaction: discord.Interaction,
        settings: Settings,
    ) -> None:
        cog = AnalyticsCog(bot)
        await run_command(cog.analytics, interaction)

        interaction.response.send_message.assert_called_once_with(  # type: ignore
            embed=ANY,
            ephemeral=True,
        )
        embed = get_last_send_message(interaction, "embed")
        assert embed["color"] == settings.INFO_EMBED_COLOR
        assert "Server Analytics" in embed["author"]["name"]
        assert "Open Analytics" in embed["description"]
        assert "expires in 10 minutes" in embed["description"]
