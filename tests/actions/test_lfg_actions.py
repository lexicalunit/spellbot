from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from spellbot.actions import LookingForGameAction
from spellbot.enums import GameFormat, GameService

if TYPE_CHECKING:
    import discord
    from spellbot import SpellBot


@pytest_asyncio.fixture
async def action(bot: SpellBot, interaction: discord.Interaction) -> LookingForGameAction:
    async with LookingForGameAction.create(bot, interaction) as action:
        return action


@pytest.mark.asyncio()
class TestLookingForGameAction:
    async def test_get_service(self, action: LookingForGameAction) -> None:
        assert await action.get_service(GameService.X_MAGE.value) == GameService.X_MAGE.value

    async def test_get_service_fallback_channel_data(self, action: LookingForGameAction) -> None:
        action.channel_data["default_service"] = GameService.X_MAGE
        assert await action.get_service(None) == GameService.X_MAGE.value

    async def test_get_service_fallback_default(self, action: LookingForGameAction) -> None:
        action.channel_data["default_service"] = None  # type: ignore
        assert await action.get_service(None) == GameService.SPELLTABLE.value

    async def test_get_format(self, action: LookingForGameAction) -> None:
        assert await action.get_format(GameFormat.PAUPER.value) == GameFormat.PAUPER.value

    async def test_get_format_fallback_channel_data(self, action: LookingForGameAction) -> None:
        action.channel_data["default_format"] = GameFormat.PAUPER
        assert await action.get_format(None) == GameFormat.PAUPER.value

    async def test_get_format_fallback_default(self, action: LookingForGameAction) -> None:
        action.channel_data["default_format"] = None  # type: ignore
        assert await action.get_format(None) == GameFormat.COMMANDER.value
