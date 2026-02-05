from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext.commands import AutoShardedBot, CommandNotFound, Context, UserInputError

from spellbot import SpellBot
from spellbot.client import ASSETS_DIR
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

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from spellbot.settings import Settings
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestSpellBot:
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
                {"service": GameService.GIRUDO.value},
                "girudo.generate_link",
                id="girudo",
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
        factories: Factories,
    ) -> None:
        assert dpy_message.guild
        guild = factories.guild.create(xid=dpy_message.guild.id)
        channel = factories.channel.create(guild=guild, xid=dpy_message.channel.id)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            deleted_at=None,
        )
        factories.post.create(
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
        factories: Factories,
    ) -> None:
        assert dpy_message.guild
        guild = factories.guild.create(xid=dpy_message.guild.id)
        channel = factories.channel.create(guild=guild, xid=dpy_message.channel.id)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
            deleted_at=None,
        )
        factories.post.create(
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
        factories: Factories,
    ) -> None:
        assert dpy_message.guild
        guild = factories.guild.create(xid=dpy_message.guild.id)
        channel = factories.channel.create(guild=guild, xid=dpy_message.channel.id)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=None,
            deleted_at=None,
        )
        factories.post.create(
            game=game,
            guild=guild,
            channel=channel,
            message_xid=dpy_message.id + 1,
        )
        await bot.handle_message_deleted(dpy_message)

        DatabaseSession.expire_all()
        assert game.deleted_at is None


@pytest.mark.asyncio
class TestSpellBotHandleVerification:
    async def test_missing_author_id(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 2
        message.channel = MagicMock()
        message.channel.type = discord.ChannelType.text
        message.flags.value = 1
        message.author = MagicMock()
        del message.author.id
        monkeypatch.setattr(bot, "handle_verification", MagicMock())

        await bot.on_message(message)

        bot.handle_verification.assert_not_called()  # type: ignore

    async def test_without_auto_verify(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
    ) -> None:
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

    async def test_with_auto_verify(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ) -> None:
        assert dpy_message.guild
        assert dpy_message.author
        assert isinstance(dpy_message.guild, discord.Guild)
        assert isinstance(dpy_message.author, discord.User)
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
    ) -> None:
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            verified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_called_once()  # type: ignore

    async def test_verified_only_when_verified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_unverified_only_when_unverified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ) -> None:
        assert dpy_message.guild
        assert isinstance(dpy_message.guild, discord.Guild)
        factories.guild.create(xid=dpy_message.guild.id)
        factories.channel.create(
            xid=dpy_message.channel.id,
            unverified_only=True,
            guild_xid=dpy_message.guild.id,
        )

        await bot.handle_verification(dpy_message)

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_unverified_only_when_verified(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ) -> None:
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

        dpy_message.delete.assert_called_once()  # type: ignore

    async def test_message_from_mod_role(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_message_from_admin_role(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
        settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_message_from_owner(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore

    async def test_message_from_administrator(
        self,
        bot: SpellBot,
        dpy_message: discord.Message,
        factories: Factories,
    ) -> None:
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

        dpy_message.delete.assert_not_called()  # type: ignore


@pytest.mark.asyncio
class TestSpellBotEmojis:
    async def test_create_application_emoji_success(
        self,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        """Test successful creation of application emoji."""
        mock_emoji = MagicMock(spec=discord.Emoji)
        create_emoji_stub = mocker.patch.object(
            bot,
            "create_application_emoji",
            AsyncMock(return_value=mock_emoji),
        )

        result = await bot._create_application_emoji("test_emoji", b"fake_image_bytes")

        assert result == mock_emoji
        create_emoji_stub.assert_called_once_with(
            name="test_emoji",
            image=b"fake_image_bytes",
        )

    async def test_create_application_emoji_exception(
        self,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        """Test exception handling in create_application_emoji."""
        mocker.patch.object(
            bot,
            "create_application_emoji",
            AsyncMock(side_effect=Exception("Discord API error")),
        )

        result = await bot._create_application_emoji("test_emoji", b"fake_image_bytes")

        assert result is None

    async def test_ensure_application_emojis_success(
        self,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        """Test successful fetching and caching of application emojis when all emojis exist."""
        emoji_dir = ASSETS_DIR / "emoji"
        emoji_files = list(emoji_dir.glob("*.png"))
        emoji_names = [f.stem for f in emoji_files]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={
                "items": [{"name": name, "id": str(i)} for i, name in enumerate(emoji_names)],
            },
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mocker.patch("spellbot.client.httpx.AsyncClient", return_value=mock_client)

        await bot._ensure_application_emojis()

        assert len(bot.emojis_cache) == len(emoji_names)

    async def test_ensure_application_emojis_creates_missing(
        self,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        """Test that missing emojis are created."""
        emoji_dir = ASSETS_DIR / "emoji"
        emoji_files = list(emoji_dir.glob("*.png"))
        num_emojis = len(emoji_files)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"items": []})  # No existing emojis

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mocker.patch("spellbot.client.httpx.AsyncClient", return_value=mock_client)

        # Create mock emoji objects for each file
        mock_emojis = []
        for f in emoji_files:
            mock_emoji = MagicMock(spec=discord.Emoji)
            mock_emoji.name = f.stem
            mock_emojis.append(mock_emoji)

        create_stub = mocker.patch.object(
            bot,
            "_create_application_emoji",
            AsyncMock(side_effect=mock_emojis),
        )

        await bot._ensure_application_emojis()

        # Should have called _create_application_emoji for each emoji file
        assert create_stub.call_count == num_emojis
        # All emojis should be in the cache
        assert len(bot.emojis_cache) == num_emojis

    async def test_ensure_application_emojis_exception(
        self,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        """Test exception handling in ensure_application_emojis."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("API error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mocker.patch("spellbot.client.httpx.AsyncClient", return_value=mock_client)

        # Should not raise, just log the exception
        await bot._ensure_application_emojis()
