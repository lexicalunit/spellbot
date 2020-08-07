from typing import cast
from unittest.mock import Mock, patch

import discord
import pytest

from spellbot.reactions import safe_clear_reactions, safe_remove_reaction

from .mocks.discord import MockDiscordMessage  # type: ignore
from .mocks.users import FRIEND  # type: ignore


@pytest.mark.asyncio
class TestReactions:
    async def test_safe_remove_reaction_removes_reaction_from_message(self):
        message = MockDiscordMessage()
        with patch.object(
            message, "remove_reaction", wraps=message.remove_reaction
        ) as fake_message:
            await safe_remove_reaction(
                cast(discord.Message, message), "emoji", cast(discord.User, FRIEND)
            )

            fake_message.assert_called_with("emoji", FRIEND)

    async def test_safe_remove_reaction_sends_message_when_forbidden_exception_is_thrown(
        self,
    ):
        message = MockDiscordMessage()
        with patch.object(
            message, "remove_reaction", wraps=message.remove_reaction
        ) as fake_message:
            fake_http_response = Mock()
            fake_http_response.status = 403
            fake_message.side_effect = discord.errors.Forbidden(
                fake_http_response, "Missing Permissions"
            )
            with patch.object(
                message.channel, "send", wraps=message.channel.send
            ) as fake_channel_send:
                await safe_remove_reaction(
                    cast(discord.Message, message), "emoji", cast(discord.User, FRIEND)
                )

                fake_channel_send.assert_called_with(
                    "I do not have permission to adjust "
                    "reactions. A server admin will need to adjust my permissions."
                )

    async def test_remove_reaction_when_http_error_is_thrown(self, caplog):
        message = MockDiscordMessage()
        response = Mock()
        response.status = 403
        with patch.object(message, "remove_reaction", wraps=message.remove_reaction) as m:
            m.side_effect = discord.errors.HTTPException(response, "BAD REQUEST")
            with patch.object(message.channel, "send", wraps=message.channel.send):
                await safe_remove_reaction(
                    cast(discord.Message, message), "emoji", cast(discord.User, FRIEND)
                )

                assert "warning: discord: could not remove reaction" in caplog.text
                assert "BAD REQUEST" in caplog.text

    async def test_clear_reactions_clears_reactions_from_message(self):
        message = MockDiscordMessage()
        with patch.object(
            message, "clear_reactions", wraps=message.clear_reactions
        ) as fake_message:
            await safe_clear_reactions(cast(discord.Message, message))

            fake_message.assert_called()

    async def test_clear_reactions_sends_message_when_forbidden_exception_is_thrown(
        self, client
    ):
        message = MockDiscordMessage()
        with patch.object(
            message, "clear_reactions", wraps=message.clear_reactions
        ) as fake_message:
            fake_http_response = Mock()
            fake_http_response.status = 403
            fake_message.side_effect = discord.errors.Forbidden(
                fake_http_response, "Missing Permissions"
            )
            with patch.object(
                message.channel, "send", wraps=message.channel.send
            ) as fake_channel_send:
                await safe_clear_reactions(cast(discord.Message, message))

                fake_channel_send.assert_called_with(
                    "I do not have permission to adjust "
                    "reactions. A server admin will need to adjust my permissions."
                )

    async def test_clear_reactions_when_http_error_is_thrown(self, caplog):
        message = MockDiscordMessage()
        fake_response = Mock()
        fake_response.status = 400
        with patch.object(message, "clear_reactions", wraps=message.clear_reactions) as m:
            m.side_effect = discord.errors.HTTPException(fake_response, "BAD REQUEST")
            with patch.object(message.channel, "send", wraps=message.channel.send):
                await safe_clear_reactions(cast(discord.Message, message))

                assert "warning: discord: could not clear reactions" in caplog.text
                assert "BAD REQUEST" in caplog.text
