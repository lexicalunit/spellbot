from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import discord
import pytest

from spellbot.errors import AdminOnlyError, GuildOnlyError
from spellbot.utils import (
    bot_can_delete_channel,
    bot_can_delete_message,
    bot_can_manage_channels,
    bot_can_read,
    bot_can_reply_to,
    bot_can_role,
    bot_can_send_messages,
    is_admin,
    is_guild,
    is_mod,
    log_warning,
    safe_permissions_for,
    user_can_moderate,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from spellbot.settings import Settings


class TestUtilsLogging:
    def test_log_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        log_warning("log-line %(foo)s", foo="foo")
        assert "log-line foo" in caplog.text
        assert "warning:" in caplog.text


@pytest.mark.asyncio
class TestUtilsPermissionsFor:
    async def test_happy_path(self) -> None:
        permissions = MagicMock(spec=discord.Permissions)
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=permissions)
        assert safe_permissions_for(channel) == permissions

    async def test_exception(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(side_effect=RuntimeError("oh no"))
        assert safe_permissions_for(channel) is None


class TestUtilsBotCanRole:
    def test_happy_path(self) -> None:
        guild = MagicMock()
        guild.me = MagicMock()
        guild.me.guild_permissions = MagicMock()
        assert bot_can_role(guild)

    def test_when_no_me(self) -> None:
        guild = MagicMock()
        guild.me = None
        assert not bot_can_role(guild)

    def test_when_no_permissions(self) -> None:
        guild = MagicMock()
        guild.me = MagicMock()
        guild.me.guild_permissions = MagicMock()
        del guild.me.guild_permissions.manage_roles
        assert not bot_can_role(guild)

    def test_when_role_greater_than_my_top_role(self) -> None:
        guild = MagicMock()
        guild.me = MagicMock()
        guild.me.guild_permissions = MagicMock()
        guild.me.top_role = 1
        role = cast("discord.Role", 10)
        assert not bot_can_role(guild, role)


class TestUtilsBotCanReplyTo:
    def test_happy_path(self) -> None:
        send_permissions = discord.Permissions(
            discord.Permissions.send_messages.flag,
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=send_permissions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert bot_can_reply_to(message)

    def test_missing_guild(self) -> None:
        send_permissions = discord.Permissions(
            discord.Permissions.send_messages.flag,
        )
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        del channel.guild
        channel.permissions_for = MagicMock(return_value=send_permissions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert not bot_can_reply_to(message)

    def test_guild_is_none(self) -> None:
        send_permissions = discord.Permissions(
            discord.Permissions.send_messages.flag,
        )
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = None
        channel.permissions_for = MagicMock(return_value=send_permissions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert not bot_can_reply_to(message)

    def test_bad_permissions(self) -> None:
        bad_permissions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permissions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert not bot_can_reply_to(message)

    def test_permissions_exception(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(side_effect=RuntimeError("oh no"))
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert not bot_can_reply_to(message)


class TestUtilsBotCanManageChannels:
    def test_happy_path(self) -> None:
        manage_permissions = discord.Permissions(
            discord.Permissions.manage_channels.flag,
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        guild.me.guild_permissions = manage_permissions
        assert bot_can_manage_channels(guild)

    def test_missing_me(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.me = None
        assert not bot_can_manage_channels(guild)

    def test_bad_permissions(self) -> None:
        manage_permissions = discord.Permissions(discord.Permissions.read_messages.flag)
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        guild.me.guild_permissions = manage_permissions
        assert not bot_can_manage_channels(guild)


class TestUtilsBotCanDeleteMessage:
    def test_happy_path(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.me = MagicMock()
        message.guild.me.guild_permissions = discord.Permissions(
            discord.Permissions.manage_messages.flag,
        )
        assert bot_can_delete_message(message)

    def test_missing_guild(self) -> None:
        message = MagicMock(spec=discord.Message)
        del message.guild
        assert not bot_can_delete_message(message)

    def test_missing_me(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.me = None
        assert not bot_can_delete_message(message)

    def test_bad_permissions(self) -> None:
        message = MagicMock(spec=discord.Message)
        message.guild = MagicMock(spec=discord.Guild)
        message.guild.me = MagicMock()
        message.guild.me.guild_permissions = discord.Permissions(
            discord.Permissions.read_messages.flag,
        )
        assert not bot_can_delete_message(message)


class TestUtilsBotCanSendMessages:
    def test_happy_path(self, mocker: MockerFixture) -> None:
        can_send = discord.Permissions(discord.Permissions.send_messages.flag)
        mocker.patch("spellbot.utils.safe_permissions_for", return_value=can_send)
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = MagicMock(spec=discord.Guild)
        assert bot_can_send_messages(channel)

    def test_missing_type(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        del channel.type
        assert not bot_can_send_messages(channel)

    def test_private_channel_type(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.private
        assert not bot_can_send_messages(channel)

    def test_no_guild(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        del channel.guild
        assert not bot_can_send_messages(channel)

    def test_no_permissions(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.utils.safe_permissions_for", return_value=None)
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = MagicMock(spec=discord.Guild)
        channel.guild.me = MagicMock()
        assert not bot_can_send_messages(channel)

    def test_bad_permissions(self, mocker: MockerFixture) -> None:
        mocker.patch("spellbot.utils.safe_permissions_for", return_value=discord.Permissions())
        channel = MagicMock(spec=discord.TextChannel)
        channel.guild = MagicMock(spec=discord.Guild)
        assert not bot_can_send_messages(channel)


class TestUtilsBotCanRead:
    def test_happy_path(self) -> None:
        read_permissions = discord.Permissions(
            discord.Permissions.read_messages.flag | discord.Permissions.read_message_history.flag,
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=read_permissions)
        assert bot_can_read(channel)

    def test_missing_channel_type(self) -> None:
        read_permissions = discord.Permissions(
            discord.Permissions.read_messages.flag | discord.Permissions.read_message_history.flag,
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        del channel.type
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=read_permissions)
        assert not bot_can_read(channel)

    def test_private_channel_type(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.private
        assert bot_can_read(channel)

    def test_missing_guild(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        del channel.guild
        assert bot_can_read(channel)

    def test_bad_permissions(self) -> None:
        bad_permissions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permissions)
        assert not bot_can_read(channel)


class TestUtilsBotCanDeleteChannel:
    def test_happy_path(self) -> None:
        del_permissions = discord.Permissions(
            discord.Permissions.manage_channels.flag,
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=del_permissions)
        assert bot_can_delete_channel(channel)

    def test_missing_channel_type(self) -> None:
        del_permissions = discord.Permissions(
            discord.Permissions.manage_channels.flag,
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        del channel.type
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=del_permissions)
        assert not bot_can_delete_channel(channel)

    def test_private_channel_type(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.private
        assert not bot_can_delete_channel(channel)

    def test_missing_guild(self) -> None:
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        del channel.guild
        assert not bot_can_delete_channel(channel)

    def test_bad_permissions(self) -> None:
        bad_permissions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permissions)
        assert not bot_can_delete_channel(channel)

    def test_none_permissions(self) -> None:
        bad_permissions = None
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permissions)
        assert not bot_can_delete_channel(channel)


class TestUtilsIsAdmin:
    def test_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.ADMIN_ROLE
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        admin_perms = discord.Permissions(
            discord.Permissions.administrator.flag,
        )
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.author = author
        assert is_admin(ctx)

    def test_missing_guild(self) -> None:
        ctx = MagicMock(spec=discord.Interaction)
        del ctx.guild
        with pytest.raises(AdminOnlyError):
            is_admin(ctx)

    def test_missing_channel(self) -> None:
        ctx = MagicMock(spec=discord.Interaction)
        del ctx.channel
        with pytest.raises(AdminOnlyError):
            is_admin(ctx)

    def test_when_user_is_owner(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 1
        channel = MagicMock(spec=discord.TextChannel)
        user = MagicMock()
        user.id = 1
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.user = user
        assert is_admin(ctx)

    def test_when_user_has_admin_role(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.ADMIN_ROLE
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        user.roles = [role]
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.user = user
        assert is_admin(ctx)

    def test_when_user_does_not_have_admin_role(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"not-{settings.ADMIN_ROLE}"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        user.roles = [role]
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.user = user
        with pytest.raises(AdminOnlyError):
            is_admin(ctx)

    def test_user_has_no_roles(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.ADMIN_ROLE
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        del user.roles
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.user = user
        with pytest.raises(AdminOnlyError):
            is_admin(ctx)


class TestUtilsIsMod:
    def test_happy_path(self, mocker: MockerFixture) -> None:
        stub = mocker.patch("spellbot.utils.user_can_moderate")
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = MagicMock(spec=discord.Guild)
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.user = MagicMock()

        is_mod(interaction)

        stub.assert_called_once_with(interaction.user, interaction.guild, interaction.channel)


class TestUtilsIsGuild:
    def test_happy_path(self) -> None:
        interaction = MagicMock(spec=discord.Interaction)
        interaction.guild = MagicMock(spec=discord.Guild)
        assert is_guild(interaction)

    def test_missing_guild(self) -> None:
        interaction = MagicMock(spec=discord.Interaction)
        del interaction.guild
        with pytest.raises(GuildOnlyError):
            is_guild(interaction)


class TestUtilsUserCanModerate:
    def test_owner_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 1
        admin_perms = discord.Permissions()
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        user = MagicMock()
        user.id = 1
        assert user_can_moderate(user, guild, channel)

    def test_admin_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        admin_perms = discord.Permissions(
            discord.Permissions.administrator.flag,
        )
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        user = MagicMock()
        user.id = 1
        assert user_can_moderate(user, guild, channel)

    def test_user_without_id(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 1
        admin_perms = discord.Permissions()
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        user = MagicMock()
        del user.id
        assert not user_can_moderate(user, guild, channel)

    def test_non_admin_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        user.roles = [role]
        assert user_can_moderate(user, guild, channel)

    def test_missing_channel(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        user = MagicMock()
        user.id = 1
        user.roles = [role]
        assert not user_can_moderate(user, guild, None)

    def test_missing_guild(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        user.roles = [role]
        assert not user_can_moderate(user, None, channel)

    def test_missing_user_roles(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        del user.roles
        assert not user_can_moderate(user, guild, channel)

    def test_when_user_does_not_have_mod_role(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.MOD_PREFIX[:2]
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        user = MagicMock()
        user.id = 1
        user.roles = [role]
        assert not user_can_moderate(user, guild, channel)
