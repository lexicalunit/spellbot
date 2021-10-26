import logging
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext.commands import errors
from discord.ext.commands.bot import Bot

from spellbot import client
from spellbot.database import DatabaseSession
from spellbot.errors import SpellbotAdminOnly, UserBannedError
from spellbot.models.channel import Channel
from spellbot.models.guild import Guild
from spellbot.models.user import User
from spellbot.models.verify import Verify
from tests.factories.channel import ChannelFactory
from tests.factories.guild import GuildFactory
from tests.factories.verify import VerifyFactory


@pytest.mark.asyncio
class TestSpellBot:
    async def test_commands_loaded(self, bot):
        assert bot.all_commands.keys() == {
            "ban",
            "unban",
        }
        assert bot.slash.subcommands.keys() == {
            "award",
            "set",
        }
        assert bot.slash.subcommands["award"].keys() == {
            "add",
            "delete",
        }
        assert bot.slash.subcommands["set"].keys() == {
            "auto_verify",
            "default_seats",
            "motd",
            "unverified_only",
            "verified_only",
        }
        assert bot.slash.components[None].keys() == {
            "join",
            "leave",
            "points",
            "refresh_setup",
            "toggle_show_links",
            "toggle_show_points",
            "toggle_voice_create",
        }
        assert bot.slash.commands.keys() == {
            "about",
            "award",
            "awards",
            "Block",
            "channels",
            "context",
            "history",
            "info",
            "leave",
            "lfg",
            "score",
            "set",
            "setup",
            "Unblock",
            "unverify",
            "unwatch",
            "verify",
            "View Score",
            "watch",
            "watched",
        }

    async def test_create_spelltable_link_mock(self, bot):
        link = await bot.create_spelltable_link()
        assert link.startswith("http://exmaple.com/game/")

    async def test_create_spelltable_link(self, bot, monkeypatch):
        bot.mock_games = False
        generate_link_mock = AsyncMock(return_value="http://mock")
        monkeypatch.setattr(client, "generate_link", generate_link_mock)
        link = await bot.create_spelltable_link()
        assert link == "http://mock"
        generate_link_mock.assert_called_once_with()

    async def test_handle_errors(self, bot, monkeypatch, caplog):
        ctx = MagicMock()

        safe_send_channel_mock = AsyncMock()
        monkeypatch.setattr(client, "safe_send_channel", safe_send_channel_mock)
        await bot.handle_errors(ctx, MagicMock(spec=errors.NoPrivateMessage))
        safe_send_channel_mock.assert_called_once_with(
            ctx,
            "This command is not supported via Direct Message.",
            hidden=True,
        )

        safe_send_channel_mock = AsyncMock()
        monkeypatch.setattr(client, "safe_send_channel", safe_send_channel_mock)
        await bot.handle_errors(ctx, MagicMock(spec=SpellbotAdminOnly))
        safe_send_channel_mock.assert_called_once_with(
            ctx,
            "You do not have permission to do that.",
            hidden=True,
        )

        safe_send_channel_mock = AsyncMock()
        monkeypatch.setattr(client, "safe_send_channel", safe_send_channel_mock)
        await bot.handle_errors(ctx, MagicMock(spec=UserBannedError))
        safe_send_channel_mock.assert_called_once_with(
            ctx,
            "You have been banned from using SpellBot.",
            hidden=True,
        )

        safe_send_channel_mock = AsyncMock()
        monkeypatch.setattr(client, "safe_send_channel", safe_send_channel_mock)
        error = RuntimeError("test-bot-unhandled-exception")
        await bot.handle_errors(ctx, error)
        assert "unhandled exception" in caplog.text
        assert "test-bot-unhandled-exception" in caplog.text

    async def test_on_component_callback_error(self, bot, monkeypatch):
        handle_errors_mock = AsyncMock()
        monkeypatch.setattr(bot, "handle_errors", handle_errors_mock)
        ctx = MagicMock()
        ex = MagicMock()
        await bot.on_component_callback_error(ctx, ex)
        handle_errors_mock.assert_called_once_with(ctx, ex)

    async def test_on_slash_command_error(self, bot, monkeypatch):
        handle_errors_mock = AsyncMock()
        monkeypatch.setattr(bot, "handle_errors", handle_errors_mock)
        ctx = MagicMock()
        ex = MagicMock()
        await bot.on_slash_command_error(ctx, ex)
        handle_errors_mock.assert_called_once_with(ctx, ex)

    async def test_legacy_prefix_cache(self, bot):
        assert bot.legacy_prefix_cache[404] == "!"

    async def test_on_message_no_guild(self, bot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = None
        await bot.on_message(message)
        super_on_message_mock.assert_called_once_with(message)

    async def test_on_message_no_channel_type(self, bot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        del message.channel.type
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_hidden(self, bot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 64
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_command(self, bot, monkeypatch, settings):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 16
        message.content = "!lfg"
        message.reply = AsyncMock()
        handle_verification_mock = AsyncMock()
        monkeypatch.setattr(bot, "handle_verification", handle_verification_mock)
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()
        handle_verification_mock.assert_called_once_with(message)
        assert message.reply.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": 5914365,
            "description": "SpellBot uses slash commands now. Just type `/` to see the"
            " list of supported commands! It may take up to one hour for these commands"
            " to appear for the first time. Also note that SpellBot's invite link has"
            " changed. Your server admin may need to re-invite the bot using the"
            f" [updated invite link]({settings.BOT_INVITE_LINK}) if slash commands do"
            " not show up after one hour.",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

    async def test_on_message_command_error(self, bot, monkeypatch, caplog, settings):
        caplog.set_level(logging.DEBUG)
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 16
        message.content = "!lfg"
        error = RuntimeError("message-reply-error")
        message.reply = AsyncMock(side_effect=error)
        handle_verification_mock = AsyncMock()
        monkeypatch.setattr(bot, "handle_verification", handle_verification_mock)
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()
        handle_verification_mock.assert_called_once_with(message)
        assert message.reply.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": 5914365,
            "description": "SpellBot uses slash commands now. Just type `/` to see the"
            " list of supported commands! It may take up to one hour for these commands"
            " to appear for the first time. Also note that SpellBot's invite link has"
            " changed. Your server admin may need to re-invite the bot using the"
            f" [updated invite link]({settings.BOT_INVITE_LINK}) if slash commands do"
            " not show up after one hour.",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }
        assert "debug: message-reply-error" in caplog.text

    async def test_on_message(self, bot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 16
        message.content = "sup"
        message.reply = AsyncMock()
        handle_verification_mock = AsyncMock()
        monkeypatch.setattr(bot, "handle_verification", handle_verification_mock)
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()
        handle_verification_mock.assert_called_once_with(message)
        message.reply.assert_not_called()


@pytest.mark.asyncio
class TestSpellBotHandleVerification:
    async def test_missing_author_id(self, bot):
        message = MagicMock()
        message.author = MagicMock()
        del message.author.id
        await bot.handle_verification(message)

    async def test_without_auto_verify(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author

        await bot.handle_verification(message)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Guild).one()
        assert found.xid == guild.id and found.name == guild.name
        found = DatabaseSession.query(Channel).one()
        assert found.xid == channel.id and found.name == channel.name
        found = DatabaseSession.query(User).one_or_none()
        assert not found
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == guild.id and found.user_xid == author.id
        assert not found.verified

    async def test_with_auto_verify(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, auto_verify=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        DatabaseSession.expire_all()
        found = DatabaseSession.query(Guild).one()
        assert found.xid == guild.id and found.name == guild.name
        found = DatabaseSession.query(Channel).one()
        assert found.xid == channel.id and found.name == channel.name
        found = DatabaseSession.query(User).one_or_none()
        assert not found
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == guild.id and found.user_xid == author.id
        assert found.verified

    async def test_verified_only_when_unverified(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, verified_only=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_called_once()

    async def test_verified_only_when_verified(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, verified_only=True, guild_xid=guild.id)
        VerifyFactory.create(guild_xid=guild.id, user_xid=author.id, verified=True)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_not_called()

    async def test_unverified_only_when_unverified(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, unverified_only=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_not_called()

    async def test_unverified_only_when_verified(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, unverified_only=True, guild_xid=guild.id)
        VerifyFactory.create(guild_xid=guild.id, user_xid=author.id, verified=True)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_called_once()

    async def test_message_from_mod_role(self, bot, settings):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        mod_role = MagicMock()
        mod_role.name = f"{settings.MOD_PREFIX}-role"
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = [mod_role]
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, verified_only=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_not_called()

    async def test_message_from_admin_role(self, bot, settings):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        admin_role = MagicMock()
        admin_role.name = settings.ADMIN_ROLE
        author = MagicMock()
        author.id = 301
        author.name = "author"
        author.roles = [admin_role]
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, verified_only=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_not_called()

    async def test_message_from_owner(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        channel.permissions_for = MagicMock(return_value=discord.Permissions())
        author = MagicMock()
        author.id = guild.owner_id
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, verified_only=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_not_called()

    async def test_message_from_administrator(self, bot):
        guild = MagicMock()
        guild.id = 101
        guild.name = "guild"
        guild.owner_id = 404
        channel = MagicMock()
        channel.id = 201
        channel.name = "channel"
        channel.guild = guild
        admin_perms = discord.Permissions(discord.Permissions.administrator.flag)
        channel.permissions_for = MagicMock(return_value=admin_perms)
        author = MagicMock()
        author.id = guild.owner_id
        author.name = "author"
        author.roles = []
        message = MagicMock()
        message.guild = guild
        message.channel = channel
        message.author = author
        message.delete = AsyncMock()
        GuildFactory.create(xid=guild.id)
        ChannelFactory.create(xid=channel.id, verified_only=True, guild_xid=guild.id)
        DatabaseSession.commit()

        await bot.handle_verification(message)

        message.delete.assert_not_called()
