from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from spellbot.actions import LookingForGameAction
from spellbot.enums import GameFormat, GameService
from tests.mocks import mock_discord_object

if TYPE_CHECKING:
    import discord
    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.models import User


@pytest_asyncio.fixture
async def action(bot: SpellBot, interaction: discord.Interaction) -> LookingForGameAction:
    async with LookingForGameAction.create(bot, interaction) as action:
        return action


@pytest.mark.asyncio
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

    async def test_execute_in_non_guild_channel(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        discord_user = mock_discord_object(user)
        mocker.patch.object(action, "guild", None)
        mocker.patch.object(action.interaction, "user", discord_user)
        stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        result = await action.execute()

        assert result is None
        stub.assert_called_once_with(
            discord_user,
            "Sorry, that command is not supported in this context.",
        )
