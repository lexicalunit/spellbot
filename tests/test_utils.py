from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import discord
import pytest
from spellbot.errors import AdminOnlyError
from spellbot.utils import (
    bot_can_delete_channel,
    bot_can_read,
    bot_can_reply_to,
    bot_can_role,
    is_admin,
    log_warning,
    user_can_moderate,
)

if TYPE_CHECKING:
    from spellbot.settings import Settings


class TestUtilsLogging:
    def test_log_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        log_warning("log-line %(foo)s", foo="foo")
        assert "log-line foo" in caplog.text
        assert "warning:" in caplog.text


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


class TestUtilsBotCanReplyTo:
    def test_happy_path(self) -> None:
        send_permisions = discord.Permissions(
            discord.Permissions.send_messages.flag,  # pylint: disable=no-member
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=send_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert bot_can_reply_to(message)

    def test_missing_guild(self) -> None:
        send_permisions = discord.Permissions(
            discord.Permissions.send_messages.flag,  # pylint: disable=no-member
        )
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        del channel.guild
        channel.permissions_for = MagicMock(return_value=send_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert not bot_can_reply_to(message)

    def test_bad_permissions(self) -> None:
        bad_permisions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permisions)
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        assert not bot_can_reply_to(message)


class TestUtilsBotCanRead:
    def test_happy_path(self) -> None:
        read_permisions = discord.Permissions(
            discord.Permissions.read_messages.flag  # pylint: disable=no-member
            | discord.Permissions.read_message_history.flag,  # pylint: disable=no-member
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=read_permisions)
        assert bot_can_read(channel)

    def test_missing_channel_type(self) -> None:
        read_permisions = discord.Permissions(
            discord.Permissions.read_messages.flag  # pylint: disable=no-member
            | discord.Permissions.read_message_history.flag,  # pylint: disable=no-member
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        del channel.type
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=read_permisions)
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
        bad_permisions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permisions)
        assert not bot_can_read(channel)


class TestUtilsBotCanDeleteChannel:
    def test_happy_path(self) -> None:
        del_permisions = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=del_permisions)
        assert bot_can_delete_channel(channel)

    def test_missing_channel_type(self) -> None:
        del_permisions = discord.Permissions(
            discord.Permissions.manage_channels.flag,  # pylint: disable=no-member
        )
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        del channel.type
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=del_permisions)
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
        bad_permisions = discord.Permissions()
        guild = MagicMock(spec=discord.Guild)
        guild.me = MagicMock()
        channel = MagicMock(spec=discord.TextChannel)
        channel.type = discord.ChannelType.text
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=bad_permisions)
        assert not bot_can_delete_channel(channel)


class TestUtilsIsAdmin:
    def test_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.ADMIN_ROLE
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        admin_perms = discord.Permissions(
            discord.Permissions.administrator.flag,  # pylint: disable=no-member
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

    def test_when_author_is_owner(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 1
        channel = MagicMock(spec=discord.TextChannel)
        author = MagicMock()
        author.id = 1
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.author = author
        assert is_admin(ctx)

    def test_when_author_has_admin_role(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.ADMIN_ROLE
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.user = author
        assert is_admin(ctx)

    def test_when_author_does_not_have_admin_role(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"not-{settings.ADMIN_ROLE}"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.author = author
        with pytest.raises(AdminOnlyError):
            is_admin(ctx)

    def test_author_has_no_roles(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.ADMIN_ROLE
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        del author.roles
        ctx = MagicMock(spec=discord.Interaction)
        ctx.guild = guild
        ctx.channel = channel
        ctx.author = author
        with pytest.raises(AdminOnlyError):
            is_admin(ctx)


class TestUtilsUserCanModerate:
    def test_owner_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 1
        admin_perms = discord.Permissions()
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        author = MagicMock()
        author.id = 1
        assert user_can_moderate(author, guild, channel)

    def test_admin_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        admin_perms = discord.Permissions(
            discord.Permissions.administrator.flag,  # pylint: disable=no-member
        )
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        author = MagicMock()
        author.id = 1
        assert user_can_moderate(author, guild, channel)

    def test_non_admin_happy_path(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        assert user_can_moderate(author, guild, channel)

    def test_missing_channel(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        assert not user_can_moderate(author, guild, None)

    def test_missing_guild(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = f"{settings.MOD_PREFIX}-whatever"
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        assert not user_can_moderate(author, None, channel)

    def test_missing_author_roles(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        del author.roles
        assert not user_can_moderate(author, guild, channel)

    def test_when_author_does_not_have_mod_role(self, settings: Settings) -> None:
        role = MagicMock()
        role.name = settings.MOD_PREFIX[:2]
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 2
        channel = MagicMock(spec=discord.TextChannel)
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 1
        author.roles = [role]
        assert not user_can_moderate(author, guild, channel)
