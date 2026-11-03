# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spellbot.views.lfg_view import GameButton, GameView

if TYPE_CHECKING:
    from spellbot import SpellBot


@pytest.mark.asyncio
class TestGameView:
    async def test_button_forwards_to_handler(self) -> None:
        handler = AsyncMock()
        button = GameButton(
            handler,
            custom_id="join",
            emoji="✋",
            label="Join",
            style=discord.ButtonStyle.blurple,
        )
        interaction = MagicMock()

        await button.callback(interaction)

        handler.assert_awaited_once_with(interaction)

    async def test_buttons_are_wired_to_view(self, bot: SpellBot) -> None:
        view = GameView(bot)

        handlers = {
            button.custom_id: button.handler
            for button in view.children
            if isinstance(button, GameButton)
        }

        assert handlers == {"join": view.join, "leave": view.leave}
