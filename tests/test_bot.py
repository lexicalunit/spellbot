from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext.commands import AutoShardedBot, CommandNotFound, Context, UserInputError

from spellbot import SpellBot
from spellbot.database import DatabaseSession
from spellbot.enums import GameService
from spellbot.errors import (
    AdminOnlyError,
    GuildBannedError,
    GuildOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from spellbot.models import Channel, GameDict, GameLinkDetails, Guild, Verify
from spellbot.utils import handle_interaction_errors

from .mixins import BaseMixin

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestSpellBot(BaseMixin):
    @pytest.mark.parametrize(
        ("mock_games", "game", "factory"),
        [
            pytest.param(
                True,
                {},
                None,
                id="mock-games",
            ),
            pytest.param(
                False,
                {"service": GameService.SPELLTABLE.value},
                "spelltable.generate_link",
                id="spellbot",
            ),
            pytest.param(
                False,
                {"service": GameService.TABLE_STREAM.value},
                "tablestream.generate_link",
                id="tablestream",
            ),
            pytest.param(
                False,
                {"service": GameService.CONVOKE.value},
                "convoke.generate_link",
                id="convoke",
            ),
            pytest.param(
                False,
                {"service": GameService.NOT_ANY.value},
                None,
                id="no-service",
            ),
        ],
    )
    async def test_create_create_game_link(
        self,
        bot: SpellBot,
        mock_games: bool,
        game: GameDict,
        factory: str | None,
        mocker: MockerFixture,
    ) -> None:
        bot.mock_games = mock_games
        if factory:
            mock = mocker.patch(f"spellbot.client.{factory}", AsyncMock())
        response = await bot.create_game_link(game)
        if factory:
            mock.assert_called_once_with(game)
        if mock_games:
            assert response.link is not None
            assert response.link.startswith("http://exmaple.com/game/")
        if game.get("service") == GameService.NOT_ANY.value:
            assert response == GameLinkDetails()

    @pytest.mark.parametrize(
        ("error", "response"),
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
                GuildBannedError(),
                "You have been banned from using SpellBot.",
                id="guild-banned",
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
    ) -> None:
        await handle_interaction_errors(interaction, error)
        interaction.user.send.assert_called_once_with(response)  # type: ignore

    async def test_handle_interaction_errors_unhandled_exception(
        self,
        interaction: discord.Interaction,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await handle_interaction_errors(interaction, RuntimeError("test-bot-unhandled-exception"))
        assert "unhandled exception" in caplog.text
        assert "test-bot-unhandled-exception" in caplog.text

    async def test_on_message_no_guild(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = None
        await bot.on_message(message)
        super_on_message_mock.assert_called_once_with(message)

    async def test_on_message_no_channel_type(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        message = MagicMock()
        message.guild = MagicMock()
        message.channel = MagicMock()
        del message.channel.type
        await bot.on_message(message)
        super_on_message_mock.assert_not_called()

    async def test_on_message_hidden(self, bot: SpellBot, monkeypatch: pytest.MonkeyPatch) -> None:
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
    ) -> None:
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        monkeypatch.setattr(bot, "handle_verification", AsyncMock())
        dpy_message.flags.value = 16
        await bot.on_message(dpy_message)
        super_on_message_mock.assert_not_called()
        bot.handle_verification.assert_called_once_with(dpy_message)  # type: ignore
        dpy_message.reply.assert_not_called()  # type: ignore

    async def test_on_message_delete_happy_path(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_handle_message_deleted = AsyncMock()
        monkeypatch.setattr(bot, "handle_message_deleted", mock_handle_message_deleted)
        await bot.on_message_delete(dpy_message)
        bot.handle_message_deleted.assert_called_once_with(dpy_message)  # type: ignore

    async def test_on_message_delete_message_without_id(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        del dpy_message.id
        mock_handle_message_deleted = AsyncMock()
        monkeypatch.setattr(bot, "handle_message_deleted", mock_handle_message_deleted)
        await bot.on_message_delete(dpy_message)
        bot.handle_message_deleted.assert_not_called()  # type: ignore

    async def test_on_command_error_command_not_found(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        context = MagicMock(spec=Context[SpellBot])
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_command_error", super_on_message_mock)
        await bot.on_command_error(context, CommandNotFound())
        super_on_message_mock.assert_not_called()

    async def test_on_command_error_user_input_error(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        context = MagicMock(spec=Context[SpellBot])
        exception = UserInputError()
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_command_error", super_on_message_mock)
        await bot.on_command_error(context, exception)
        super_on_message_mock.assert_called_once_with(context, exception)

    async def test_handle_message_deleted_when_game_not_started(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
    ) -> None:
        assert dpy_message.guild
        guild = self.factories.guild.create(xid=dpy_message.guild.id)
        channel = self.factories.channel.create(guild=guild, xid=dpy_message.channel.id)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            deleted_at=None,
        )
        self.factories.post.create(
            game=game,
            guild=guild,
            channel=channel,
            message_xid=dpy_message.id,
        )
        await bot.handle_message_deleted(dpy_message)

        DatabaseSession.expire_all()
        assert game.deleted_at is not None

    async def test_handle_message_deleted_when_game_is_started(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
    ) -> None:
        assert dpy_message.guild
        guild = self.factories.guild.create(xid=dpy_message.guild.id)
        channel = self.factories.channel.create(guild=guild, xid=dpy_message.channel.id)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
            deleted_at=None,
        )
        self.factories.post.create(
            game=game,
            guild=guild,
            channel=channel,
            message_xid=dpy_message.id,
        )
        await bot.handle_message_deleted(dpy_message)

        DatabaseSession.expire_all()
        assert game.deleted_at is None

    async def test_handle_message_deleted_when_message_not_found(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
    ) -> None:
        assert dpy_message.guild
        guild = self.factories.guild.create(xid=dpy_message.guild.id)
        channel = self.factories.channel.create(guild=guild, xid=dpy_message.channel.id)
        game = self.factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            deleted_at=None,
        )
        self.factories.post.create(
            game=game,
            guild=guild,
            channel=channel,
            message_xid=dpy_message.id + 1,
        )
        await bot.handle_message_deleted(dpy_message)

        DatabaseSession.expire_all()
        assert game.deleted_at is None


@pytest.mark.asyncio
class TestSpellBotHandleVerification(BaseMixin):
    async def test_missing_author_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

        self.bot.handle_verification.assert_not_called()  # type: ignore

    async def test_without_auto_verify(self, dpy_message: discord.Message) -> None:
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

    async def test_with_auto_verify(self, dpy_message: discord.Message) -> None:
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

    async def test_verified_only_when_unverified(self, dpy_message: discord.Message) -> None:
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()  # type: ignore

    async def test_verified_only_when_verified(self, dpy_message: discord.Message) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_unverified_only_when_unverified(self, dpy_message: discord.Message) -> None:
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        self.factories.guild.create(xid=dpy_message.guild.id)
        self.factories.channel.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await self.bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_unverified_only_when_verified(self, dpy_message: discord.Message) -> None:
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

        dpy_message.delete.assert_called_once()  # type: ignore

    async def test_message_from_mod_role(
        self,
        dpy_message: discord.Message,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_message_from_admin_role(
        self,
        dpy_message: discord.Message,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_message_from_owner(
        self,
        dpy_message: discord.Message,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_message_from_administrator(self, dpy_message: discord.Message) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore
