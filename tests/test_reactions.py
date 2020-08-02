from unittest.mock import patch

import pytest

from spellbot.reactions import safe_clear_reactions, safe_remove_reaction

from .mocks.discord import MockDiscordMessage  # type: ignore
from .mocks.users import FRIEND  # type: ignore


@pytest.mark.asyncio
class TestReactions:
    async def test_safe_remove_reaction_removes_reaction_from_message(
        self, channel_maker
    ):
        message = MockDiscordMessage()
        with patch.object(
            message, "remove_reaction", wraps=message.remove_reaction
        ) as monkey:
            await safe_remove_reaction(message, "emoji", FRIEND)

            monkey.assert_called_with("emoji", FRIEND)

    async def test_clear_reactions_clears_reactions_from_message(self, channel_maker):
        message = MockDiscordMessage()
        with patch.object(
            message, "clear_reactions", wraps=message.clear_reactions
        ) as monkey:
            await safe_clear_reactions(message)

            monkey.assert_called()
