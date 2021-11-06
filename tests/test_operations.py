import logging
from typing import Union
from unittest.mock import AsyncMock, MagicMock, Mock

import discord
import pytest
from discord.errors import DiscordException
from discord_slash.context import ComponentContext

from spellbot.operations import (
    safe_add_role,
    safe_create_category_channel,
    safe_create_invite,
    safe_create_voice_channel,
    safe_delete_channel,
    safe_ensure_voice_category,
    safe_fetch_guild,
    safe_fetch_message,
    safe_fetch_text_channel,
    safe_fetch_user,
    safe_message_reply,
    safe_send_user,
    safe_update_embed,
    safe_update_embed_origin,
)
from spellbot.utils import CANT_SEND_CODE
from tests.mocks import mock_client


@pytest.mark.asyncio
class TestOperationsFetchUser:
    async def test_cached(self):
        user = MagicMock()
        user.id = 1
        client = mock_client(users=[user])
        found = await safe_fetch_user(client, user.id)
        assert found is user

    async def test_uncached(self, monkeypatch):
        user = MagicMock()
        user.id = 1
        client = mock_client(users=[user])
        mock_get_user = MagicMock(return_value=None)
        monkeypatch.setattr(client, "get_user", mock_get_user)
        found = await safe_fetch_user(client, user.id)
        assert found is user


@pytest.mark.asyncio
class TestOperationsFetchGuild:
    async def test_cached(self):
        guild = MagicMock()
        guild.id = 1
        client = mock_client(guilds=[guild])
        found = await safe_fetch_guild(client, guild.id)
        assert found is guild

    async def test_uncached(self, monkeypatch):
        guild = MagicMock()
        guild.id = 1
        client = mock_client(guilds=[guild])
        mock_get_guild = MagicMock(return_value=None)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)
        found = await safe_fetch_guild(client, guild.id)
        assert found is guild


@pytest.mark.asyncio
class TestOperationsFetchTextChannel:
    async def test_cached(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 1
        client = mock_client(channels=[channel])
        found = await safe_fetch_text_channel(client, 2, channel.id)
        assert found is channel

    async def test_uncached(self, monkeypatch):
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 1
        client = mock_client(channels=[channel])
        mock_get_channel = MagicMock(return_value=None)
        monkeypatch.setattr(client, "get_channel", mock_get_channel)
        found = await safe_fetch_text_channel(client, 2, channel.id)
        assert found is channel

    async def test_non_text(self):
        channel = MagicMock(spec=discord.DMChannel)
        channel.id = 1
        client = mock_client(channels=[channel])
        found = await safe_fetch_text_channel(client, 2, channel.id)
        assert found is None

    async def test_uncached_non_text(self, monkeypatch):
        channel = MagicMock(spec=discord.DMChannel)
        channel.id = 1
        client = mock_client(channels=[channel])
        mock_get_channel = MagicMock(return_value=None)
        monkeypatch.setattr(client, "get_channel", mock_get_channel)
        found = await safe_fetch_text_channel(client, 2, channel.id)
        assert found is None


@pytest.mark.asyncio
class TestOperationsFetchMessage:
    read_perms = discord.Permissions(
        discord.Permissions.read_messages.flag
        | discord.Permissions.read_message_history.flag
    )

    async def test_happy_path(self):
        message = MagicMock()
        message.id = 1

        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.fetch_message = AsyncMock(return_value=message)
        channel.permissions_for = MagicMock(return_value=self.read_perms)

        found = await safe_fetch_message(channel, guild.id, message.id)
        assert found is message

    async def test_not_text(self):
        message = MagicMock()
        message.id = 1

        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.VoiceChannel)
        channel.id = 3
        channel.type = discord.ChannelType.voice
        channel.guild = guild
        channel.fetch_message = AsyncMock(return_value=message)
        channel.permissions_for = MagicMock(return_value=self.read_perms)

        found = await safe_fetch_message(channel, guild.id, message.id)
        assert found is None

    async def test_no_permissions(self):
        message = MagicMock()
        message.id = 1

        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.fetch_message = AsyncMock(return_value=message)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())

        found = await safe_fetch_message(channel, guild.id, message.id)
        assert found is None


@pytest.mark.asyncio
class TestOperationsUpdateEmbed:
    async def test_happy_path(self):
        message = MagicMock(spec=discord.Message)
        message.edit = AsyncMock()
        await safe_update_embed(message, "content", flags=1)
        message.edit.assert_called_once_with("content", flags=1)


@pytest.mark.asyncio
class TestOperationsUpdateEmbedOrigin:
    async def test_happy_path(self):
        ctx = MagicMock(spec=ComponentContext)
        ctx.edit_origin = AsyncMock()
        ctx.origin_message_id = 1
        await safe_update_embed_origin(ctx, "content", hidden=True)
        ctx.edit_origin.assert_called_once_with("content", hidden=True)


@pytest.mark.asyncio
class TestOperationsCreateCategoryChannel:
    async def test_happy_path(self):
        guild = MagicMock()
        guild.id = 1
        guild.create_category_channel = AsyncMock()
        client = mock_client(guilds=[guild])
        await safe_create_category_channel(client, guild.id, "name")
        guild.create_category_channel.assert_called_once_with("name")

    async def test_uncached(self, monkeypatch):
        guild = MagicMock()
        guild.id = 1
        guild.create_category_channel = AsyncMock()
        client = mock_client(guilds=[guild])
        mock_get_guild = MagicMock(return_value=None)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)
        await safe_create_category_channel(client, guild.id, "name")
        guild.create_category_channel.assert_called_once_with("name")

    async def test_not_found(self):
        guild = MagicMock()
        guild.id = 1
        guild.create_category_channel = AsyncMock()
        client = mock_client()
        await safe_create_category_channel(client, guild.id, "name")
        guild.create_category_channel.assert_not_called()


@pytest.mark.asyncio
class TestOperationsCreateVoiceChannel:
    async def test_happy_path(self):
        guild = MagicMock()
        guild.id = 1
        guild.create_voice_channel = AsyncMock()
        category = MagicMock()
        client = mock_client(guilds=[guild])
        await safe_create_voice_channel(client, guild.id, "name", category=category)
        guild.create_voice_channel.assert_called_once_with("name", category=category)

    async def test_uncached(self, monkeypatch):
        guild = MagicMock()
        guild.id = 1
        guild.create_voice_channel = AsyncMock()
        category = MagicMock()
        client = mock_client(guilds=[guild])
        mock_get_guild = MagicMock(return_value=None)
        monkeypatch.setattr(client, "get_guild", mock_get_guild)
        await safe_create_voice_channel(client, guild.id, "name", category=category)
        guild.create_voice_channel.assert_called_once_with("name", category=category)

    async def test_not_found(self):
        guild = MagicMock()
        guild.id = 1
        guild.create_voice_channel = AsyncMock()
        category = MagicMock()
        client = mock_client()
        await safe_create_voice_channel(client, guild.id, "name", category=category)
        guild.create_voice_channel.assert_not_called()


@pytest.mark.asyncio
class TestOperationsCreateInvite:
    async def test_happy_path(self):
        guild = MagicMock()
        guild.id = 1
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.id = 2
        invite = MagicMock()
        invite.url = "http://url"
        channel.create_invite = AsyncMock(return_value=invite)
        url = await safe_create_invite(channel, guild.id, 10)
        channel.create_invite.assert_awaited_once_with(max_age=10)
        assert url == invite.url


@pytest.mark.asyncio
class TestOperationsDeleteChannel:
    delete_perms = discord.Permissions(discord.Permissions.manage_channels.flag)

    async def test_happy_path(self):
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 3
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock()
        channel.permissions_for = MagicMock(return_value=self.delete_perms)

        assert await safe_delete_channel(channel, guild.id)
        channel.delete.assert_called_once_with()

    async def test_missing_channel_id(self):
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        del channel.id
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock()
        channel.permissions_for = MagicMock(return_value=self.delete_perms)

        assert not await safe_delete_channel(channel, guild.id)
        channel.delete.assert_not_called()

    async def test_missing_permissions(self):
        guild = MagicMock(spec=discord.Guild)
        guild.id = 2
        guild.me = MagicMock()

        channel = MagicMock(spec=discord.TextChannel)
        del channel.id
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.delete = AsyncMock()
        channel.permissions_for = MagicMock(return_value=discord.Permissions())

        assert not await safe_delete_channel(channel, guild.id)
        channel.delete.assert_not_called()


@pytest.mark.asyncio
class TestOperationsSendUser:
    async def test_happy_path(self):
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.send = AsyncMock()
        embed = discord.Embed()
        await safe_send_user(user, "content", embed=embed)
        user.send.assert_called_once_with("content", embed=embed)

    async def test_not_sendable(self, caplog):
        user = Mock()
        del user.send
        user.__str__ = lambda self: "user#1234"  # type: ignore
        await safe_send_user(user, "content")
        assert "no send method on user user#1234" in caplog.text

    async def test_forbidden(self, caplog):
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.send = AsyncMock(side_effect=discord.errors.Forbidden(MagicMock(), "msg"))
        await safe_send_user(user, "content")
        assert "not allowed to send message to user#1234" in caplog.text

    async def test_cant_send(self, caplog):
        exception = discord.errors.HTTPException(MagicMock(), "msg")
        setattr(exception, "code", CANT_SEND_CODE)
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "not allowed to send message to user#1234" in caplog.text

    async def test_http_failure(self, caplog):
        exception = discord.errors.HTTPException(MagicMock(), "msg")
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "failed to send message to user user#1234" in caplog.text

    async def test_server_error(self, caplog):
        exception = discord.errors.DiscordServerError(MagicMock(), "msg")
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "discord server error sending to user user#1234" in caplog.text

    async def test_invalid_argument(self, caplog):
        exception = discord.errors.InvalidArgument(MagicMock(), "msg")
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.send = AsyncMock(side_effect=exception)
        await safe_send_user(user, "content")
        assert "could not send message to user user#1234" in caplog.text


@pytest.mark.asyncio
class TestOperationsAddRole:
    role_perms = discord.Permissions(discord.Permissions.manage_roles.flag)

    async def test_happy_path(self):
        member = MagicMock(spec=Union[discord.User, discord.Member])
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        role = MagicMock()
        role.name = "role"
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        member.add_roles.assert_called_once_with(role)

    async def test_no_roles_attribute(self):
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.id = 101
        member = MagicMock(spec=Union[discord.User, discord.Member])
        member.id = user.id
        member.roles = []
        member.add_roles = AsyncMock()
        role = MagicMock()
        role.name = "role"
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.get_member = MagicMock(return_value=member)
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        member.add_roles.assert_called_once_with(role)

    async def test_no_member(self, caplog):
        user = MagicMock(spec=Union[discord.User, discord.Member])
        user.__str__ = lambda self: "user#1234"  # type: ignore
        user.id = 101
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.get_member = MagicMock(return_value=None)
        await safe_add_role(user, guild, "role")
        guild.get_member.assert_called_once()
        assert (
            f"warning: in guild {guild.id}, could not add role:"
            " could not find member: user#1234"
        ) in caplog.text

    async def test_no_role(self, caplog):
        member = MagicMock(spec=Union[discord.User, discord.Member])
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.roles = []
        await safe_add_role(member, guild, "role")
        assert (
            f"warning: in guild {guild.id}, could not add role:"
            " could not find role: role"
        ) in caplog.text

    async def test_no_permissions(self, caplog):
        member = MagicMock(spec=Union[discord.User, discord.Member])
        member.id = 101
        member.roles = []
        member.add_roles = AsyncMock()
        role = MagicMock()
        role.name = "role"
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = discord.Permissions()
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        assert (
            f"warning: in guild {guild.id}, could not add role:"
            " no permissions to add role: role"
        ) in caplog.text

    async def test_forbidden(self, caplog):
        member = MagicMock(spec=Union[discord.User, discord.Member])
        member.id = 101
        member.roles = []
        member.__str__ = lambda self: "user#1234"  # type: ignore
        exception = discord.errors.Forbidden(MagicMock(), "msg")
        member.add_roles = AsyncMock(side_effect=exception)
        role = MagicMock()
        role.name = "role"
        guild = MagicMock(spec=discord.Guild)
        guild.id = 201
        guild.me = MagicMock()
        guild.me.guild_permissions = self.role_perms
        guild.roles = [role]
        await safe_add_role(member, guild, "role")
        assert (
            f"warning: in guild {guild.id},"
            f" could not add role to member user#1234: {exception}"
        ) in caplog.text


@pytest.mark.asyncio
class TestOperationsMessageReply:
    async def test_happy_path(self):
        send_permisions = discord.Permissions(discord.Permissions.send_messages.flag)
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=send_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        message.reply = AsyncMock()
        embed = MagicMock(spec=discord.Embed)

        await safe_message_reply(message, "content", embed=embed)
        message.reply.assert_called_once_with("content", embed=embed)

    async def test_bad_permissions(self):
        bad_permisions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        message.reply = AsyncMock()
        embed = MagicMock(spec=discord.Embed)

        await safe_message_reply(message, "content", embed=embed)
        message.reply.assert_not_called()

    async def test_reply_failure(self, caplog):
        caplog.set_level(logging.DEBUG)
        send_permisions = discord.Permissions(discord.Permissions.send_messages.flag)
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=send_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        error = RuntimeError("something-failed")
        message.reply = AsyncMock(side_effect=error)
        embed = MagicMock(spec=discord.Embed)

        await safe_message_reply(message, "content", embed=embed)
        message.reply.assert_called_once_with("content", embed=embed)
        assert "something-failed" in caplog.text


@pytest.mark.asyncio
class TestEnsureVoiceCategory:
    async def test_available_exists(self):
        channel = MagicMock(spec=discord.VoiceChannel)
        category = MagicMock(spec=discord.CategoryChannel)
        category.name = "voice-channels"
        category.channels = [channel]
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category]
        guild.create_category_channel = AsyncMock()
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is category
        guild.create_category_channel.assert_not_called()

    async def test_none_exists(self):
        new_category = MagicMock(spec=discord.CategoryChannel)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = []
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels")

    async def test_none_available(self):
        new_category = MagicMock(spec=discord.CategoryChannel)
        channel = MagicMock(spec=discord.VoiceChannel)
        category = MagicMock(spec=discord.CategoryChannel)
        category.name = "voice-channels"
        category.channels = [channel] * 50
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category]
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels 2")

    async def test_create_failure(self):
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = []
        guild.create_category_channel = AsyncMock(side_effect=DiscordException())
        client = mock_client(guilds=[guild])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is None
        guild.create_category_channel.assert_called_once_with("voice-channels")

    async def test_missing_numbered_category(self):
        new_category = MagicMock(spec=discord.CategoryChannel)
        new_category.name = "voice-channels 2"
        channel1 = MagicMock(spec=discord.VoiceChannel)
        category1 = MagicMock(spec=discord.CategoryChannel)
        category1.name = "voice-channels 1"
        category1.channels = [channel1] * 50
        channel3 = MagicMock(spec=discord.VoiceChannel)
        category3 = MagicMock(spec=discord.CategoryChannel)
        category3.name = "voice-channels 3"
        category3.channels = [channel3]
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category1, category3]
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild], categories=[category1, category3])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels 2")

    async def test_available_has_bad_name(self):
        new_category = MagicMock(spec=discord.CategoryChannel)
        new_category.name = "voice-channels"
        channel = MagicMock(spec=discord.VoiceChannel)
        category = MagicMock(spec=discord.CategoryChannel)
        category.name = "voice-channels xyz"
        category.channels = [channel]
        guild = MagicMock(spec=discord.Guild)
        guild.id = 101
        guild.categories = [category]
        guild.create_category_channel = AsyncMock(return_value=new_category)
        client = mock_client(guilds=[guild], categories=[category])
        result = await safe_ensure_voice_category(client, guild.id, "voice-channels")
        assert result is new_category
        guild.create_category_channel.assert_called_once_with("voice-channels")

    async def test_no_guild(self):
        client = mock_client()
        result = await safe_ensure_voice_category(client, 404, "voice-channels")
        assert result is None
