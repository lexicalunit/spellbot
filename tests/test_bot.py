from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext.commands.bot import AutoShardedBot
from spellbot import SpellBot, client
from spellbot.database import DatabaseSession
from spellbot.errors import (
    AdminOnlyError,
    GuildOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from spellbot.models import Channel, Guild, Verify
from spellbot.utils import handle_interaction_errors

from .mixins import BaseMixin


@pytest.mark.asyncio
class TestSpellBot:
    async def test_create_spelltable_link_mock(self, bot: SpellBot):
        link = await bot.create_spelltable_link()
        assert link is not None
        assert link.startswith("http://exmaple.com/game/")

    async def test_create_spelltable_link(self, bot: SpellBot, monkeypatch: pytest.MonkeyPatch):
        bot.mock_games = False
        generate_link_mock = AsyncMock(return_value="http://mock")
        monkeypatch.setattr(client, "generate_link", generate_link_mock)
        link = await bot.create_spelltable_link()
        assert link == "http://mock"
        generate_link_mock.assert_called_once_with()

    @pytest.mark.parametrize(
        "error, response",
        [
            pytest.param(
                app_commands.NoPrivateMessage(),
                "This command is not supported in DMs.",
                id="no-private-message",
            ),
            pytest.param(
                AdminOnlyError(),
                "You do not have permission to do that.",
                id="admin-only",
            ),
            pytest.param(
                GuildOnlyError(),
                "This command only works in a guild.",
                id="guild-only",
            ),
            pytest.param(
                UserBannedError(),
                "You have been banned from using SpellBot.",
                id="user-banned",
            ),
            pytest.param(
                UserUnverifiedError(),
                "Only verified users can do that here.",
                id="user-unverified",
            ),
            pytest.param(
                UserVerifiedError(),
                "Only unverified users can do that here.",
                id="user-verified",
            ),
        ],
    )
    async def test_handle_interaction_errors(
        self,
        interaction: discord.Interaction,
        error: Exception,
        response: str,
    ):
        await handle_interaction_errors(interaction, error)
        interaction.user.send.assert_called_once_with(response)

    async def test_handle_interaction_errors_unhandled_exception(
        self,
        interaction: discord.Interaction,
        caplog: pytest.LogCaptureFixture,
    ):
        await handle_interaction_errors(interaction, RuntimeError("test-bot-unhandled-exception"))
        assert "unhandled exception" in caplog.text
        assert "test-bot-unhandled-exception" in caplog.text

    async def test_on_message_no_guild(self, bot: SpellBot, monkeypatch: pytest.MonkeyPatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = None
        await bot.on_message(message)
        super_on_message_mock.assert_called_once_with(message)

    async def test_on_message_no_channel_type(self, bot: SpellBot, monkeypatch: pytest.MonkeyPatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        del message.channel.type
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_hidden(self, bot: SpellBot, monkeypatch: pytest.MonkeyPatch):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 64
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_happy_path(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ):
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        monkeypatch.setattr(bot, "handle_verification", AsyncMock())
        dpy_message.flags.value = 16
        await bot.on_message(dpy_message)
        super_on_message_mock.assert_not_called()
        bot.handle_verification.assert_called_once_with(dpy_message)
        dpy_message.reply.assert_not_called()


@pytest.mark.asyncio
class TestSpellBotHandleVerification(BaseMixin):
    async def test_missing_author_id(self, monkeypatch: pytest.MonkeyPatch):
        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 2
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 1
        message.author = MagicMock()
        del message.author.id
        monkeypatch.setattr(self.bot, "handle_verification", MagicMock())

        await self.bot.on_message(message)

        self.bot.handle_verification.assert_not_called()

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

    async def test_message_from_mod_role(
        self,
        dpy_message: discord.Message,
        monkeypatch: pytest.MonkeyPatch,
    ):
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
        monkeypatch: pytest.MonkeyPatch,
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

    async def test_message_from_owner(
        self,
        dpy_message: discord.Message,
        monkeypatch: pytest.MonkeyPatch,
    ):
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
