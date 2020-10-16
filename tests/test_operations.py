from typing import cast
from unittest.mock import MagicMock, Mock

import discord
import pytest

from spellbot.constants import GREEN_CHECK, RED_X
from spellbot.operations import (
    safe_clear_reactions,
    safe_create_category_channel,
    safe_create_invite,
    safe_create_voice_channel,
    safe_delete_channel,
    safe_delete_message,
    safe_edit_message,
    safe_fetch_channel,
    safe_fetch_message,
    safe_fetch_user,
    safe_react_error,
    safe_react_ok,
    safe_remove_reaction,
    safe_send_user,
)

from .mocks import AsyncMock
from .mocks.discord import MockDiscordMessage, MockTextChannel, MockVoiceChannel
from .mocks.users import FRIEND


@pytest.fixture
def mock_message(monkeypatch):
    message = MockDiscordMessage()
    monkeypatch.setattr(message, "add_reaction", AsyncMock())
    monkeypatch.setattr(message, "clear_reactions", AsyncMock())
    monkeypatch.setattr(message, "delete", AsyncMock())
    monkeypatch.setattr(message, "edit", AsyncMock())
    monkeypatch.setattr(message, "remove_reaction", AsyncMock())
    monkeypatch.setattr(message.channel, "fetch_message", AsyncMock())
    monkeypatch.setattr(message.channel, "send", AsyncMock())
    return message


@pytest.mark.asyncio
class TestOperations:
    async def test_safe_remove_reaction(self, mock_message):
        await safe_remove_reaction(
            cast(discord.Message, mock_message), "emoji", cast(discord.User, FRIEND)
        )

        mock_message.remove_reaction.assert_called_with("emoji", FRIEND)

    async def test_safe_remove_reaction_error_forbidden(self, mock_message):
        http_response = Mock()
        http_response.status = 403
        mock_message.remove_reaction.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )

        await safe_remove_reaction(
            cast(discord.Message, mock_message), "emoji", cast(discord.User, FRIEND)
        )

        mock_message.channel.send.assert_called_with(
            "I do not have permission to adjust reactions."
            " A server admin will need to adjust my permissions."
        )

    async def test_safe_remove_reaction_error_bad_request(self, mock_message, caplog):
        response = Mock()
        response.status = 400
        mock_message.remove_reaction.side_effect = discord.errors.HTTPException(
            response, "BAD REQUEST"
        )

        await safe_remove_reaction(
            cast(discord.Message, mock_message), "emoji", cast(discord.User, FRIEND)
        )

        assert "warning: discord (DM): could not remove reaction" in caplog.text
        assert "BAD REQUEST" in caplog.text

    async def test_safe_clear_reactions(self, mock_message):
        await safe_clear_reactions(cast(discord.Message, mock_message))

        mock_message.clear_reactions.assert_called()

    async def test_safe_clear_reactions_error_forbidden(self, mock_message, client):
        http_response = Mock()
        http_response.status = 403
        mock_message.clear_reactions.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )

        await safe_clear_reactions(cast(discord.Message, mock_message))

        mock_message.channel.send.assert_called_with(
            "I do not have permission to adjust reactions."
            " A server admin will need to adjust my permissions."
        )

    async def test_safe_clear_reactions_error_bad_request(self, mock_message, caplog):
        response = Mock()
        response.status = 400
        mock_message.clear_reactions.side_effect = discord.errors.HTTPException(
            response, "BAD REQUEST"
        )

        await safe_clear_reactions(cast(discord.Message, mock_message))

        assert "warning: discord (DM): could not clear reactions" in caplog.text
        assert "BAD REQUEST" in caplog.text

    async def test_safe_react_ok(self, mock_message):
        await safe_react_ok(cast(discord.Message, mock_message))

        mock_message.add_reaction.assert_called_with(GREEN_CHECK)

    async def test_safe_react_ok_error_forbidden(self, mock_message, client):
        http_response = Mock()
        http_response.status = 403
        mock_message.add_reaction.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )

        await safe_react_ok(cast(discord.Message, mock_message))

        mock_message.channel.send.assert_called_with(
            "I do not have permission to adjust reactions."
            " A server admin will need to adjust my permissions."
        )

    async def test_safe_react_ok_error_bad_request(self, mock_message, caplog):
        response = Mock()
        response.status = 400
        mock_message.add_reaction.side_effect = discord.errors.HTTPException(
            response, "BAD REQUEST"
        )

        await safe_react_ok(cast(discord.Message, mock_message))

        assert "warning: discord (DM): could not react to message" in caplog.text
        assert "BAD REQUEST" in caplog.text

    async def test_safe_react_error(self, mock_message):
        await safe_react_error(cast(discord.Message, mock_message))

        mock_message.add_reaction.assert_called_with(RED_X)

    async def test_safe_react_error_error_forbidden(self, mock_message, client):
        http_response = Mock()
        http_response.status = 403
        mock_message.add_reaction.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )

        await safe_react_error(cast(discord.Message, mock_message))

        mock_message.channel.send.assert_called_with(
            "I do not have permission to adjust reactions."
            " A server admin will need to adjust my permissions."
        )

    async def test_safe_react_error_error_bad_request(self, mock_message, caplog):
        response = Mock()
        response.status = 400
        mock_message.add_reaction.side_effect = discord.errors.HTTPException(
            response, "BAD REQUEST"
        )

        await safe_react_error(cast(discord.Message, mock_message))

        assert "warning: discord (DM): could not react to message" in caplog.text
        assert "BAD REQUEST" in caplog.text

    async def test_safe_fetch_message(self, mock_message):
        await safe_fetch_message(
            mock_message.channel, mock_message.id, mock_message.channel.guild.id
        )

        mock_message.channel.fetch_message.assert_called_with(mock_message.id)

    async def test_safe_fetch_message_bad_channel(self, mock_message, monkeypatch):
        monkeypatch.setattr(
            mock_message,
            "channel",
            discord.VoiceChannel(
                state=None,
                guild=mock_message.channel.guild,
                data={"id": 0, "name": "name", "position": "position"},
            ),
        )

        message = await safe_fetch_message(
            mock_message.channel, mock_message.id, mock_message.channel.guild.id
        )

        assert message is None

    async def test_safe_fetch_message_error_forbidden(self, mock_message, caplog):
        http_response = Mock()
        http_response.status = 403
        mock_message.channel.fetch_message.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )

        await safe_fetch_message(
            mock_message.channel, mock_message.id, mock_message.channel.guild.id
        )

        guild_id = mock_message.channel.guild.id
        assert (
            f"warning: discord (guild {guild_id}): could not fetch message" in caplog.text
        )
        assert "Missing Permissions" in caplog.text

    async def test_safe_fetch_channel_when_cached(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        mock_get_channel = MagicMock()
        mock_get_channel.return_value = mock_channel
        monkeypatch.setattr(client, "get_channel", mock_get_channel)

        channel = await safe_fetch_channel(client, mock_channel.id, mock_channel.guild.id)

        assert channel is mock_channel
        mock_get_channel.assert_called_with(mock_channel.id)

    async def test_safe_fetch_channel_when_not_cached(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        mock_get_channel = MagicMock()
        mock_get_channel.return_value = None
        monkeypatch.setattr(client, "get_channel", mock_get_channel)
        mock_fetch_channel = AsyncMock()
        mock_fetch_channel.return_value = mock_channel
        monkeypatch.setattr(client, "fetch_channel", mock_fetch_channel)

        channel = await safe_fetch_channel(client, mock_channel.id, mock_channel.guild.id)

        assert channel is mock_channel
        mock_get_channel.assert_called_with(mock_channel.id)
        mock_fetch_channel.assert_called_with(mock_channel.id)

    async def test_safe_fetch_channel_when_not_cached_error(
        self, client, monkeypatch, caplog
    ):
        mock_channel = MockTextChannel(1, "general", [])
        mock_get_channel = MagicMock()
        mock_get_channel.return_value = None
        monkeypatch.setattr(client, "get_channel", mock_get_channel)
        mock_fetch_channel = AsyncMock()
        http_response = Mock()
        http_response.status = 403
        mock_fetch_channel.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )
        monkeypatch.setattr(client, "fetch_channel", mock_fetch_channel)

        await safe_fetch_channel(client, mock_channel.id, mock_channel.guild.id)

        guild_id = mock_channel.guild.id
        assert (
            f"warning: discord (guild {guild_id}): could not fetch channel" in caplog.text
        )
        assert "Missing Permissions" in caplog.text

    async def test_safe_fetch_user_when_cached(self, client, monkeypatch):
        mock_get_user = MagicMock()
        mock_get_user.return_value = FRIEND
        monkeypatch.setattr(client, "get_user", mock_get_user)

        user = await safe_fetch_user(client, FRIEND.id)

        assert user is FRIEND
        mock_get_user.assert_called_with(FRIEND.id)

    async def test_safe_fetch_user_when_not_cached(self, client, monkeypatch):
        mock_get_user = MagicMock()
        mock_get_user.return_value = None
        monkeypatch.setattr(client, "get_user", mock_get_user)
        mock_fetch_user = AsyncMock()
        mock_fetch_user.return_value = FRIEND
        monkeypatch.setattr(client, "fetch_user", mock_fetch_user)

        user = await safe_fetch_user(client, FRIEND.id)

        assert user is FRIEND
        mock_get_user.assert_called_with(FRIEND.id)
        mock_fetch_user.assert_called_with(FRIEND.id)

    async def test_safe_fetch_user_when_not_cached_error(
        self, client, monkeypatch, caplog
    ):
        mock_get_user = MagicMock()
        mock_get_user.return_value = None
        monkeypatch.setattr(client, "get_user", mock_get_user)
        mock_fetch_user = AsyncMock()
        http_response = Mock()
        http_response.status = 403
        mock_fetch_user.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )
        monkeypatch.setattr(client, "fetch_user", mock_fetch_user)

        await safe_fetch_user(client, FRIEND.id)

        assert "warning: discord: could not fetch user" in caplog.text
        assert "Missing Permissions" in caplog.text

    async def test_safe_edit_message(self, mock_message):
        await safe_edit_message(cast(discord.Message, mock_message))

        mock_message.edit.assert_called_with(reason=None)

    async def test_safe_edit_message_error_bad_request(self, mock_message, caplog):
        response = Mock()
        response.status = 400
        mock_message.edit.side_effect = discord.errors.HTTPException(
            response, "BAD REQUEST"
        )

        await safe_edit_message(cast(discord.Message, mock_message))

        assert "warning: discord (DM): could not edit message" in caplog.text
        assert "BAD REQUEST" in caplog.text

    async def test_safe_delete_message(self, mock_message):
        await safe_delete_message(cast(discord.Message, mock_message))

        mock_message.delete.assert_called_with()

    async def test_safe_delete_message_error_bad_request(self, mock_message, caplog):
        response = Mock()
        response.status = 400
        mock_message.delete.side_effect = discord.errors.HTTPException(
            response, "BAD REQUEST"
        )

        await safe_delete_message(cast(discord.Message, mock_message))

        assert "warning: discord (DM): could not delete message" in caplog.text
        assert "BAD REQUEST" in caplog.text

    async def test_safe_send_user(self, client, monkeypatch):
        await safe_send_user(cast(discord.User, FRIEND), content="test")

        assert FRIEND.last_sent_response == "test"

    async def test_safe_send_user_error(self, client, monkeypatch, caplog):
        mock_send = AsyncMock()
        http_response = Mock()
        http_response.status = 500
        mock_send.side_effect = discord.errors.HTTPException(
            http_response, "Internal Server Error"
        )
        monkeypatch.setattr(FRIEND, "send", mock_send)

        await safe_send_user(cast(discord.User, FRIEND), content="test")

        assert "warning: discord (DM): could not send message to user" in caplog.text
        assert "Internal Server Error" in caplog.text

    async def test_safe_send_user_blocked(self, client, monkeypatch, caplog):
        mock_send = AsyncMock()
        http_response = Mock()
        http_response.status = 403
        mock_send.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )
        monkeypatch.setattr(FRIEND, "send", mock_send)

        await safe_send_user(cast(discord.User, FRIEND), content="test")

        assert "warning: discord (DM): could not send message to user" not in caplog.text
        assert "Missing Permissions" not in caplog.text

    async def test_safe_create_voice_channel(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        chan = await safe_create_voice_channel(client, mock_channel.guild.id, "whatever")

        assert chan.id == 1

    async def test_safe_create_voice_channel_create_error(
        self, client, monkeypatch, caplog
    ):
        mock_channel = MockTextChannel(1, "general", [])
        mock_guild = mock_channel.guild
        mock_guild_id = mock_channel.guild.id

        mock_get_guild = Mock(return_value=mock_guild)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)

        mock_create_voice_channel = AsyncMock()
        http_response = Mock()
        http_response.status = 403
        mock_create_voice_channel.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )
        monkeypatch.setattr(mock_guild, "create_voice_channel", mock_create_voice_channel)

        chan = await safe_create_voice_channel(client, mock_channel.guild.id, "whatever")

        assert chan is None
        assert (
            f"warning: discord (guild {mock_guild_id}): could not create voice channel"
            in caplog.text
        )
        assert "Missing Permissions" in caplog.text

    async def test_safe_create_voice_channel_guild_error(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        mock_get_guild = Mock(return_value=None)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)

        chan = await safe_create_voice_channel(client, mock_channel.guild.id, "whatever")

        assert chan is None

    async def test_safe_delete_channel(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        await safe_delete_channel(
            cast(discord.TextChannel, mock_channel), mock_channel.guild.id
        )

        mock_channel.delete.assert_called_once_with()

    async def test_safe_delete_channel_error(self, client, monkeypatch, caplog):
        mock_channel = MockTextChannel(1, "general", [])
        mock_guild_id = mock_channel.guild.id

        mock_delete = AsyncMock()
        http_response = Mock()
        http_response.status = 403
        mock_delete.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )
        monkeypatch.setattr(mock_channel, "delete", mock_delete)

        await safe_delete_channel(
            cast(discord.TextChannel, mock_channel), mock_channel.guild.id
        )

        assert (
            f"warning: discord (guild {mock_guild_id}): could not delete channel"
            in caplog.text
        )
        assert "Missing Permissions" in caplog.text

    async def test_safe_create_category_channel(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        category = await safe_create_category_channel(
            client, mock_channel.guild.id, "whatever"
        )

        assert category.id == 2

    async def test_safe_create_category_channel_create_error(
        self, client, monkeypatch, caplog
    ):
        mock_channel = MockTextChannel(1, "general", [])
        mock_guild = mock_channel.guild
        mock_guild_id = mock_channel.guild.id

        mock_get_guild = Mock(return_value=mock_guild)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)

        mock_create_category_channel = AsyncMock()
        http_response = Mock()
        http_response.status = 403
        mock_create_category_channel.side_effect = discord.errors.Forbidden(
            http_response, "Missing Permissions"
        )
        monkeypatch.setattr(
            mock_guild, "create_category_channel", mock_create_category_channel
        )

        cateogry = await safe_create_category_channel(
            client, mock_channel.guild.id, "whatever"
        )

        assert cateogry is None
        assert (
            f"warning: discord (guild {mock_guild_id}): could not create category channel"
            in caplog.text
        )
        assert "Missing Permissions" in caplog.text

    async def test_safe_create_category_channel_guild_error(self, client, monkeypatch):
        mock_channel = MockTextChannel(1, "general", [])
        mock_get_guild = Mock(return_value=None)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)

        category = await safe_create_category_channel(
            client, mock_channel.guild.id, "whatever"
        )

        assert category is None

    async def test_safe_create_invite(self, client, monkeypatch):
        mock_channel = MockVoiceChannel(1, "general", [])
        await safe_create_invite(
            cast(discord.VoiceChannel, mock_channel), mock_channel.guild.id
        )

        mock_channel.create_invite.assert_called_once_with(max_age=0)

    async def test_safe_create_invite_error(self, client, monkeypatch, caplog):
        mock_channel = MockVoiceChannel(1, "general", [])
        mock_guild_id = mock_channel.guild.id

        mock_create_invite = AsyncMock()
        http_response = Mock()
        http_response.status = 400
        mock_create_invite.side_effect = discord.errors.HTTPException(
            http_response, "BAD REQUEST"
        )
        monkeypatch.setattr(mock_channel, "create_invite", mock_create_invite)

        await safe_create_invite(
            cast(discord.VoiceChannel, mock_channel), mock_channel.guild.id
        )

        assert (
            f"warning: discord (guild {mock_guild_id}): could create channel invite"
            in caplog.text
        )
        assert "BAD REQUEST" in caplog.text
