import logging
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext.commands import errors
from discord.ext.commands.bot import Bot
from discord_slash.context import InteractionContext, SlashContext

from spellbot import client
from spellbot.database import DatabaseSession
from spellbot.errors import (
    AdminOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from spellbot.models import Channel, Guild, Verify
from tests.mixins import BaseMixin


@pytest.mark.asyncio
class TestSpellBot(BaseMixin):
    async def test_commands_loaded(self):
        assert self.bot.all_commands.keys() == {
            "ban",
            "unban",
        }
        assert self.bot.slash.subcommands.keys() == {
            "award",
            "set",
        }
        assert self.bot.slash.subcommands["award"].keys() == {
            "add",
            "delete",
        }
        assert self.bot.slash.subcommands["set"].keys() == {
            "auto_verify",
            "channel_motd",
            "default_seats",
            "motd",
            "unverified_only",
            "verified_only",
        }
        assert self.bot.slash.components[None].keys() == {
            "join",
            "leave",
            "points",
            "refresh_setup",
            "toggle_show_links",
            "toggle_show_points",
            "toggle_voice_create",
        }
        assert self.bot.slash.commands.keys() == {
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
            "power",
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

    async def test_create_spelltable_link_mock(self):
        link = await self.bot.create_spelltable_link()
        assert link is not None
        assert link.startswith("http://exmaple.com/game/")

    async def test_create_spelltable_link(self, monkeypatch):
        self.bot.mock_games = False
        generate_link_mock = AsyncMock(return_value="http://mock")
        monkeypatch.setattr(client, "generate_link", generate_link_mock)
        link = await self.bot.create_spelltable_link()
        assert link == "http://mock"
        generate_link_mock.assert_called_once_with()

    async def test_handle_error_dm(self, ctx: InteractionContext):
        await self.bot.handle_errors(ctx, MagicMock(spec=errors.NoPrivateMessage))
        ctx.send.assert_called_once_with(
            "This command is not supported via Direct Message.",
            hidden=True,
        )

    async def test_handle_error_permissions(self, ctx: InteractionContext):
        await self.bot.handle_errors(ctx, MagicMock(spec=AdminOnlyError))
        ctx.send.assert_called_once_with(
            "You do not have permission to do that.",
            hidden=True,
        )

    async def test_handle_error_banned(self, ctx: InteractionContext):
        await self.bot.handle_errors(ctx, MagicMock(spec=UserBannedError))
        ctx.send.assert_called_once_with(
            "You have been banned from using SpellBot.",
            hidden=True,
        )

    async def test_handle_error_unverified(self, ctx: InteractionContext):
        await self.bot.handle_errors(ctx, MagicMock(spec=UserUnverifiedError))
        ctx.send.assert_called_once_with(
            "Only verified users can do that in this channel.",
            hidden=True,
        )

    async def test_handle_error_verified(self, ctx: InteractionContext):
        await self.bot.handle_errors(ctx, MagicMock(spec=UserVerifiedError))
        ctx.send.assert_called_once_with(
            "Only unverified users can do that in this channel.",
            hidden=True,
        )

    async def test_handle_error_unhandled_exception(self, caplog):
        ctx = MagicMock()
        await self.bot.handle_errors(ctx, RuntimeError("test-bot-unhandled-exception"))
        assert "unhandled exception" in caplog.text
        assert "test-bot-unhandled-exception" in caplog.text

    async def test_on_component_callback_error(self, monkeypatch):
        monkeypatch.setattr(self.bot, "handle_errors", AsyncMock())
        ex = MagicMock()
        ctx = MagicMock()
        await self.bot.on_component_callback_error(ctx, ex)
        self.bot.handle_errors.assert_called_once_with(ctx, ex)

    async def test_on_slash_command_error(self, ctx: SlashContext, monkeypatch):
        monkeypatch.setattr(self.bot, "handle_errors", AsyncMock())
        ex = MagicMock()
        await self.bot.on_slash_command_error(ctx, ex)
        self.bot.handle_errors.assert_called_once_with(ctx, ex)

    async def test_legacy_prefix_cache(self):
        assert self.bot.legacy_prefix_cache[404] == "!"

    async def test_on_message_no_guild(self, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = None
        await self.bot.on_message(message)
        super_on_message_mock.assert_called_once_with(message)

    async def test_on_message_no_channel_type(self, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        del message.channel.type
        await self.bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_hidden(self, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 64
        await self.bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_command(self, monkeypatch):
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
        monkeypatch.setattr(self.bot, "handle_verification", handle_verification_mock)
        await self.bot.on_message(message)
        super_on_message_mock.assert_not_called()
        handle_verification_mock.assert_called_once_with(message)
        assert message.reply.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                "SpellBot uses [slash commands](https://discord.com/blog"
                "/slash-commands-are-here) now. Type `/` to see the"
                " list of commands! If you don't see any, please [re-invite the"
                f" bot using its new invite link]({self.settings.BOT_INVITE_LINK})."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
        }

    async def test_on_message_command_error(self, monkeypatch, caplog):
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
        monkeypatch.setattr(self.bot, "handle_verification", handle_verification_mock)
        await self.bot.on_message(message)
        super_on_message_mock.assert_not_called()
        handle_verification_mock.assert_called_once_with(message)
        assert message.reply.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": self.settings.EMBED_COLOR,
            "description": (
                "SpellBot uses [slash commands](https://discord.com/blog"
                "/slash-commands-are-here) now. Type `/` to see the"
                " list of commands! If you don't see any, please [re-invite the"
                f" bot using its new invite link]({self.settings.BOT_INVITE_LINK})."
            ),
            "thumbnail": {"url": self.settings.ICO_URL},
            "type": "rich",
        }
        assert "debug: message-reply-error" in caplog.text

    async def test_on_message(self, dpy_message: discord.Message, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        monkeypatch.setattr(self.bot, "handle_verification", AsyncMock())
        dpy_message.flags.value = 16
        await self.bot.on_message(dpy_message)
        super_on_message_mock.assert_not_called()
        self.bot.handle_verification.assert_called_once_with(dpy_message)
        dpy_message.reply.assert_not_called()


@pytest.mark.asyncio
class TestSpellBotHandleVerification(BaseMixin):
    async def test_missing_author_id(self):
        message = MagicMock()
        message.author = MagicMock()
        del message.author.id
        await self.bot.handle_verification(message)

    async def test_without_auto_verify(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert dpy_message.author
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        await self.bot.handle_verification(dpy_message)

        DatabaseSession.expire_all()
        assert DatabaseSession.query(Guild).one().xid == dpy_message.guild.id
        assert DatabaseSession.query(Channel).one().xid == dpy_message.channel.id
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == dpy_message.guild.id
        assert found.user_xid == dpy_message.author.id
        assert not found.verified

    async def test_with_auto_verify(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert dpy_message.author
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            auto_verify=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        DatabaseSession.expire_all()
        assert DatabaseSession.query(Guild).one().xid == dpy_message.guild.id
        assert DatabaseSession.query(Channel).one().xid == dpy_message.channel.id
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == dpy_message.guild.id
        assert found.user_xid == dpy_message.author.id
        assert found.verified

    async def test_verified_only_when_unverified(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()

    async def test_verified_only_when_verified(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )
        self.factories.verify.create(
            guild_xid=dpy_message.guild.id,
            user_xid=dpy_message.author.id,
            verified=True,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_unverified_only_when_unverified(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_unverified_only_when_verified(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )
        self.factories.verify.create(
            guild_xid=dpy_message.guild.id,
            user_xid=dpy_message.author.id,
            verified=True,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()

    async def test_message_from_mod_role(self, dpy_message: discord.Message, monkeypatch):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        mod_role = MagicMock()
        mod_role.name = f"{self.settings.MOD_PREFIX}-role"
        monkeypatch.setattr(dpy_message.author, "roles", [mod_role])
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_admin_role(
        self,
        dpy_message: discord.Message,
        monkeypatch,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        admin_role = MagicMock()
        admin_role.name = self.settings.ADMIN_ROLE
        monkeypatch.setattr(dpy_message.author, "roles", [admin_role])
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_owner(self, dpy_message: discord.Message, monkeypatch):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        monkeypatch.setattr(dpy_message.author, "id", dpy_message.guild.owner_id)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_administrator(self, dpy_message: discord.Message):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        admin_perms = discord.Permissions(discord.Permissions.administrator.flag)
        dpy_message.channel.permissions_for = MagicMock(return_value=admin_perms)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()
