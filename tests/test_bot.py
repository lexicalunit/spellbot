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
            "game",
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

    async def test_handle_error_dm(self, bot, ctx):
        await bot.handle_errors(ctx, MagicMock(spec=errors.NoPrivateMessage))
        ctx.send.assert_called_once_with(
            "This command is not supported via Direct Message.",
            hidden=True,
        )

    async def test_handle_error_permissions(self, bot, ctx):
        await bot.handle_errors(ctx, MagicMock(spec=SpellbotAdminOnly))
        ctx.send.assert_called_once_with(
            "You do not have permission to do that.",
            hidden=True,
        )

    async def test_handle_error_banned(self, bot, ctx):
        await bot.handle_errors(ctx, MagicMock(spec=UserBannedError))
        ctx.send.assert_called_once_with(
            "You have been banned from using SpellBot.",
            hidden=True,
        )

    async def test_handle_error_unhandled_exception(self, bot, ctx, caplog):
        await bot.handle_errors(ctx, RuntimeError("test-bot-unhandled-exception"))
        assert "unhandled exception" in caplog.text
        assert "test-bot-unhandled-exception" in caplog.text

    async def test_on_component_callback_error(self, bot, monkeypatch, ctx):
        monkeypatch.setattr(bot, "handle_errors", AsyncMock())
        ex = MagicMock()
        await bot.on_component_callback_error(ctx, ex)
        bot.handle_errors.assert_called_once_with(ctx, ex)

    async def test_on_slash_command_error(self, bot, monkeypatch, ctx):
        monkeypatch.setattr(bot, "handle_errors", AsyncMock())
        ex = MagicMock()
        await bot.on_slash_command_error(ctx, ex)
        bot.handle_errors.assert_called_once_with(ctx, ex)

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
            "color": settings.EMBED_COLOR,
            "description": (
                "SpellBot uses [slash commands](https://discord.com/blog"
                "/slash-commands-are-here) now. Type `/` to see the"
                " list of commands! If you don't see any, please [re-invite the"
                f" bot using its new invite link]({settings.BOT_INVITE_LINK})."
            ),
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
            "color": settings.EMBED_COLOR,
            "description": (
                "SpellBot uses [slash commands](https://discord.com/blog"
                "/slash-commands-are-here) now. Type `/` to see the"
                " list of commands! If you don't see any, please [re-invite the"
                f" bot using its new invite link]({settings.BOT_INVITE_LINK})."
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }
        assert "debug: message-reply-error" in caplog.text

    async def test_on_message(self, bot, monkeypatch, dpy_message):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        monkeypatch.setattr(bot, "handle_verification", AsyncMock())
        dpy_message.flags.value = 16
        await bot.on_message(dpy_message)
        super_on_message_mock.assert_not_called()
        bot.handle_verification.assert_called_once_with(dpy_message)
        dpy_message.reply.assert_not_called()


@pytest.mark.asyncio
class TestSpellBotHandleVerification:
    async def test_missing_author_id(self, bot):
        message = MagicMock()
        message.author = MagicMock()
        del message.author.id
        await bot.handle_verification(message)

    async def test_without_auto_verify(self, bot, dpy_message):
        await bot.handle_verification(dpy_message)

        DatabaseSession.expire_all()
        assert DatabaseSession.query(Guild).one().xid == dpy_message.guild.id
        assert DatabaseSession.query(Channel).one().xid == dpy_message.channel.id
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == dpy_message.guild.id
        assert found.user_xid == dpy_message.author.id
        assert not found.verified

    async def test_with_auto_verify(self, bot, dpy_message):
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            auto_verify=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        DatabaseSession.expire_all()
        assert DatabaseSession.query(Guild).one().xid == dpy_message.guild.id
        assert DatabaseSession.query(Channel).one().xid == dpy_message.channel.id
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == dpy_message.guild.id
        assert found.user_xid == dpy_message.author.id
        assert found.verified

    async def test_verified_only_when_unverified(self, bot, dpy_message):
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()

    async def test_verified_only_when_verified(self, bot, dpy_message):
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )
        VerifyFactory.create(
            guild_xid=dpy_message.guild.id,
            user_xid=dpy_message.author.id,
            verified=True,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_unverified_only_when_unverified(self, bot, dpy_message):
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_unverified_only_when_verified(self, bot, dpy_message):
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )
        VerifyFactory.create(
            guild_xid=dpy_message.guild.id,
            user_xid=dpy_message.author.id,
            verified=True,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()

    async def test_message_from_mod_role(self, bot, settings, dpy_message):
        mod_role = MagicMock()
        mod_role.name = f"{settings.MOD_PREFIX}-role"
        dpy_message.author.roles = [mod_role]
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_admin_role(self, bot, settings, dpy_message):
        admin_role = MagicMock()
        admin_role.name = settings.ADMIN_ROLE
        dpy_message.author.roles = [admin_role]
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_owner(self, bot, dpy_message):
        dpy_message.author.id = dpy_message.guild.owner_id
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_administrator(self, bot, dpy_message):
        admin_perms = discord.Permissions(discord.Permissions.administrator.flag)
        dpy_message.channel.permissions_for = MagicMock(return_value=admin_perms)
        GuildFactory.create(xid=dpy_message.guild.id)
        ChannelFactory.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()
