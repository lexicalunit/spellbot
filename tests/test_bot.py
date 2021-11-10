import logging
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext.commands import errors
from discord.ext.commands.bot import Bot
from discord_slash.context import InteractionContext, SlashContext

from spellbot import SpellBot, client
from spellbot.database import DatabaseSession
from spellbot.errors import SpellbotAdminOnly, UserBannedError
from spellbot.models import Channel, Guild, Verify
from spellbot.settings import Settings
from tests.fixtures import Factories


@pytest.mark.asyncio
class TestSpellBot:
    async def test_commands_loaded(self, bot: SpellBot):
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
            "channel_motd",
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

    async def test_create_spelltable_link_mock(self, bot: SpellBot):
        link = await bot.create_spelltable_link()
        assert link is not None
        assert link.startswith("http://exmaple.com/game/")

    async def test_create_spelltable_link(self, bot: SpellBot, monkeypatch):
        bot.mock_games = False
        generate_link_mock = AsyncMock(return_value="http://mock")
        monkeypatch.setattr(client, "generate_link", generate_link_mock)
        link = await bot.create_spelltable_link()
        assert link == "http://mock"
        generate_link_mock.assert_called_once_with()

    async def test_handle_error_dm(self, bot: SpellBot, ctx: InteractionContext):
        await bot.handle_errors(ctx, MagicMock(spec=errors.NoPrivateMessage))
        ctx.send.assert_called_once_with(
            "This command is not supported via Direct Message.",
            hidden=True,
        )

    async def test_handle_error_permissions(self, bot: SpellBot, ctx: InteractionContext):
        await bot.handle_errors(ctx, MagicMock(spec=SpellbotAdminOnly))
        ctx.send.assert_called_once_with(
            "You do not have permission to do that.",
            hidden=True,
        )

    async def test_handle_error_banned(self, bot: SpellBot, ctx: InteractionContext):
        await bot.handle_errors(ctx, MagicMock(spec=UserBannedError))
        ctx.send.assert_called_once_with(
            "You have been banned from using SpellBot.",
            hidden=True,
        )

    async def test_handle_error_unhandled_exception(
        self,
        bot: SpellBot,
        caplog,
    ):
        ctx = MagicMock()
        await bot.handle_errors(ctx, RuntimeError("test-bot-unhandled-exception"))
        assert "unhandled exception" in caplog.text
        assert "test-bot-unhandled-exception" in caplog.text

    async def test_on_component_callback_error(
        self,
        bot: SpellBot,
        monkeypatch,
    ):
        monkeypatch.setattr(bot, "handle_errors", AsyncMock())
        ex = MagicMock()
        ctx = MagicMock()
        await bot.on_component_callback_error(ctx, ex)
        bot.handle_errors.assert_called_once_with(ctx, ex)

    async def test_on_slash_command_error(
        self,
        bot: SpellBot,
        ctx: SlashContext,
        monkeypatch,
    ):
        monkeypatch.setattr(bot, "handle_errors", AsyncMock())
        ex = MagicMock()
        await bot.on_slash_command_error(ctx, ex)
        bot.handle_errors.assert_called_once_with(ctx, ex)

    async def test_legacy_prefix_cache(self, bot: SpellBot):
        assert bot.legacy_prefix_cache[404] == "!"

    async def test_on_message_no_guild(self, bot: SpellBot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = None
        await bot.on_message(message)
        super_on_message_mock.assert_called_once_with(message)

    async def test_on_message_no_channel_type(self, bot: SpellBot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        del message.channel.type
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_hidden(self, bot: SpellBot, monkeypatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(Bot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 64
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_command(
        self,
        bot: SpellBot,
        settings: Settings,
        monkeypatch,
    ):
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

    async def test_on_message_command_error(
        self,
        bot: SpellBot,
        settings: Settings,
        monkeypatch,
        caplog,
    ):
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

    async def test_on_message(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        monkeypatch,
    ):
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
    async def test_missing_author_id(self, bot: SpellBot):
        message = MagicMock()
        message.author = MagicMock()
        del message.author.id
        await bot.handle_verification(message)

    async def test_without_auto_verify(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
    ):
        assert dpy_message.guild
        assert dpy_message.author
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        await bot.handle_verification(dpy_message)

        DatabaseSession.expire_all()
        assert DatabaseSession.query(Guild).one().xid == dpy_message.guild.id
        assert DatabaseSession.query(Channel).one().xid == dpy_message.channel.id
        found = DatabaseSession.query(Verify).one()
        assert found.guild_xid == dpy_message.guild.id
        assert found.user_xid == dpy_message.author.id
        assert not found.verified

    async def test_with_auto_verify(self, bot: SpellBot, dpy_message, factories):
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
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

    async def test_verified_only_when_unverified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()

    async def test_verified_only_when_verified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )
        factories.verify.create(
            guild_xid=dpy_message.guild.id,
            user_xid=dpy_message.author.id,
            verified=True,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_unverified_only_when_unverified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_unverified_only_when_verified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )
        factories.verify.create(
            guild_xid=dpy_message.guild.id,
            user_xid=dpy_message.author.id,
            verified=True,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()

    async def test_message_from_mod_role(
        self,
        bot: SpellBot,
        settings: Settings,
        dpy_message: discord.Message,
        factories: Factories,
        monkeypatch,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        mod_role = MagicMock()
        mod_role.name = f"{settings.MOD_PREFIX}-role"
        monkeypatch.setattr(dpy_message.author, "roles", [mod_role])
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_admin_role(
        self,
        bot: SpellBot,
        settings: Settings,
        dpy_message: discord.Message,
        factories: Factories,
        monkeypatch,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        admin_role = MagicMock()
        admin_role.name = settings.ADMIN_ROLE
        monkeypatch.setattr(dpy_message.author, "roles", [admin_role])
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_owner(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
        monkeypatch,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        monkeypatch.setattr(dpy_message.author, "id", dpy_message.guild.owner_id)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()

    async def test_message_from_administrator(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ):
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        admin_perms = discord.Permissions(discord.Permissions.administrator.flag)
        dpy_message.channel.permissions_for = MagicMock(return_value=admin_perms)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()
