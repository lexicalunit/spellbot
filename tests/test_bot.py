# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext.commands import AutoShardedBot, CommandNotFound, Context, UserInputError
from sqlalchemy import select

from spellbot import SpellBot
from spellbot.client import ASSETS_DIR, TTLDict
from spellbot.data import GameLinkDetails
from spellbot.database import DatabaseSession
from spellbot.enums import GameService
from spellbot.errors import (
    AdminOnlyError,
    GuildBannedError,
    GuildOnlyError,
    ModOnlyError,
    UserBannedError,
    UserUnverifiedError,
    UserVerifiedError,
)
from spellbot.models import Channel, Game, Guild, Verify
from spellbot.utils import handle_interaction_errors
from tests.mocks import build_role, create_mock_game

if TYPE_CHECKING:
    from decoy import Decoy
    from pytest_mock import MockerFixture

    from spellbot.settings import Settings
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestSpellBot:
    @pytest.mark.parametrize(
        ("mock_games", "service", "factory"),
        [
            pytest.param(
                True,
                GameService.CONVOKE.value,
                None,
                id="mock-games",
            ),
            pytest.param(
                False,
                GameService.TABLE_STREAM.value,
                "tablestream.generate_link",
                id="tablestream",
            ),
            pytest.param(
                False,
                GameService.CONVOKE.value,
                "convoke.generate_link",
                id="convoke",
            ),
            pytest.param(
                False,
                GameService.GIRUDO.value,
                "girudo.generate_link",
                id="girudo",
            ),
            pytest.param(
                False,
                GameService.EDHLAB.value,
                "edhlab.generate_link",
                id="edhlab",
            ),
            pytest.param(
                False,
                GameService.PLAYGROUP_LIVE.value,
                "playgroup_live.generate_link",
                id="playgroup-live",
            ),
            pytest.param(
                False,
                GameService.NOT_ANY.value,
                None,
                id="no-service",
            ),
        ],
    )
    async def test_create_create_game_link(
        self,
        bot: SpellBot,
        mock_games: bool,
        service: int,
        factory: str | None,
        mocker: MockerFixture,
    ) -> None:
        game = create_mock_game(service=service)
        bot.mock_games = mock_games
        if factory:
            mock = mocker.patch(f"spellbot.client.{factory}", AsyncMock())
        response = await bot.create_game_link(game)
        if factory:
            if factory in ("convoke.generate_link", "playgroup_live.generate_link"):
                mock.assert_called_once_with(game, None)
            else:
                mock.assert_called_once_with(game)
        if mock_games:
            assert response.link is not None
            assert response.link.startswith("http://example.com/game/")
        if service == GameService.NOT_ANY.value:
            assert response == GameLinkDetails()

    @pytest.mark.parametrize(
        ("mock_games", "service", "expected"),
        [
            pytest.param(False, GameService.CONVOKE.value, True, id="convoke"),
            pytest.param(True, GameService.CONVOKE.value, False, id="mock-games"),
            pytest.param(False, GameService.TABLE_STREAM.value, False, id="other-service"),
        ],
    )
    async def test_update_game_players(
        self,
        bot: SpellBot,
        mock_games: bool,
        service: int,
        expected: bool,
        mocker: MockerFixture,
    ) -> None:
        game = create_mock_game(service=service)
        bot.mock_games = mock_games
        mock = mocker.patch("spellbot.client.convoke.update_players", AsyncMock())
        await bot.update_game_players(game, {1: "123456"})
        if expected:
            mock.assert_awaited_once_with(game, {1: "123456"})
        else:
            mock.assert_not_called()

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
                ModOnlyError(),
                "You do not have permission to do that.",
                id="mod-only",
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
            pytest.param(
                app_commands.CommandOnCooldown(app_commands.Cooldown(1, 60), 25.0),
                "Please try again in 25s.",
                id="cooldown",
            ),
        ],
    )
    async def test_handle_interaction_errors(
        self,
        decoy: Decoy,
        decoy_member: discord.Member,
        error: Exception,
        response: str,
    ) -> None:
        interaction = decoy.mock(cls=discord.Interaction)
        interaction.user = decoy_member
        await handle_interaction_errors(interaction, error)
        decoy.verify(await decoy_member.send(response))

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
        decoy: Decoy,
        decoy_message: discord.Message,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        super_on_message_mock = AsyncMock()
        monkeypatch.setattr(AutoShardedBot, "on_message", super_on_message_mock)
        handle_verification = AsyncMock()
        monkeypatch.setattr(bot, "handle_verification", handle_verification)
        decoy_message.flags.value = 16
        await bot.on_message(decoy_message)
        super_on_message_mock.assert_not_called()
        handle_verification.assert_called_once_with(decoy_message)
        decoy.verify(await decoy_message.reply(), times=0, ignore_extra_args=True)

    async def test_on_message_delete_happy_path(
        self,
        dpy_message: discord.Message,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_handle_message_deleted = AsyncMock()
        monkeypatch.setattr(bot, "handle_message_deleted", mock_handle_message_deleted)
        await bot.on_message_delete(dpy_message)
        mock_handle_message_deleted.assert_called_once_with(dpy_message)

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
        mock_handle_message_deleted.assert_not_called()

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
        refreshed = await DatabaseSession.get(Game, game.id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None

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
        handle_verification = MagicMock()
        monkeypatch.setattr(bot, "handle_verification", handle_verification)

        await bot.on_message(message)

        handle_verification.assert_not_called()

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
        guild = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == dpy_message.guild.id))
        ).scalar_one()
        assert guild.xid == dpy_message.guild.id
        channel = (
            await DatabaseSession.execute(
                select(Channel).where(Channel.xid == dpy_message.channel.id),
            )
        ).scalar_one()
        assert channel.xid == dpy_message.channel.id
        found = (
            await DatabaseSession.execute(
                select(Verify).where(
                    Verify.guild_xid == dpy_message.guild.id,
                    Verify.user_xid == dpy_message.author.id,
                ),
            )
        ).scalar_one()
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
        guild = (
            await DatabaseSession.execute(select(Guild).where(Guild.xid == dpy_message.guild.id))
        ).scalar_one()
        assert guild.xid == dpy_message.guild.id
        channel = (
            await DatabaseSession.execute(
                select(Channel).where(Channel.xid == dpy_message.channel.id),
            )
        ).scalar_one()
        assert channel.xid == dpy_message.channel.id
        found = (
            await DatabaseSession.execute(
                select(Verify).where(
                    Verify.guild_xid == dpy_message.guild.id,
                    Verify.user_xid == dpy_message.author.id,
                ),
            )
        ).scalar_one()
        assert found.guild_xid == dpy_message.guild.id
        assert found.user_xid == dpy_message.author.id
        assert found.verified

    async def test_verified_only_when_unverified(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        factories: Factories,
    ) -> None:
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(xid=decoy_channel.id, verified_only=True, guild_xid=decoy_guild.id)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete())

    async def test_verified_only_when_verified(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        decoy_member: discord.Member,
        factories: Factories,
    ) -> None:
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(xid=decoy_channel.id, verified_only=True, guild_xid=decoy_guild.id)
        factories.verify.create(guild_xid=decoy_guild.id, user_xid=decoy_member.id, verified=True)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete(), times=0, ignore_extra_args=True)

    async def test_unverified_only_when_unverified(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        factories: Factories,
    ) -> None:
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(
            xid=decoy_channel.id,
            unverified_only=True,
            guild_xid=decoy_guild.id,
        )

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete(), times=0, ignore_extra_args=True)

    async def test_unverified_only_when_verified(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        decoy_member: discord.Member,
        factories: Factories,
    ) -> None:
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(
            xid=decoy_channel.id,
            unverified_only=True,
            guild_xid=decoy_guild.id,
        )
        factories.verify.create(guild_xid=decoy_guild.id, user_xid=decoy_member.id, verified=True)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete())

    async def test_message_from_mod_role(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        decoy_member: discord.Member,
        factories: Factories,
        settings: Settings,
    ) -> None:
        mod_role = build_role(decoy_guild, role_id=1, name=f"{settings.MOD_PREFIX}-role")
        decoy.when(decoy_member.roles).then_return([mod_role])
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(xid=decoy_channel.id, verified_only=True, guild_xid=decoy_guild.id)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete(), times=0, ignore_extra_args=True)

    async def test_message_from_admin_role(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        decoy_member: discord.Member,
        factories: Factories,
        settings: Settings,
    ) -> None:
        admin_role = build_role(decoy_guild, role_id=1, name=settings.ADMIN_ROLE)
        decoy.when(decoy_member.roles).then_return([admin_role])
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(xid=decoy_channel.id, verified_only=True, guild_xid=decoy_guild.id)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete(), times=0, ignore_extra_args=True)

    async def test_message_from_owner(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        decoy_member: discord.Member,
        factories: Factories,
    ) -> None:
        assert decoy_guild.owner_id is not None
        decoy_member.id = decoy_guild.owner_id
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(xid=decoy_channel.id, verified_only=True, guild_xid=decoy_guild.id)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete(), times=0, ignore_extra_args=True)

    async def test_message_from_administrator(
        self,
        bot: SpellBot,
        decoy: Decoy,
        decoy_message: discord.Message,
        decoy_guild: discord.Guild,
        decoy_channel: discord.TextChannel,
        decoy_member: discord.Member,
        factories: Factories,
    ) -> None:
        admin_perms = discord.Permissions(discord.Permissions.administrator.flag)
        decoy.when(decoy_channel.permissions_for(decoy_member)).then_return(admin_perms)
        factories.guild.create(xid=decoy_guild.id)
        factories.channel.create(xid=decoy_channel.id, verified_only=True, guild_xid=decoy_guild.id)

        await bot.handle_verification(decoy_message)

        decoy.verify(await decoy_message.delete(), times=0, ignore_extra_args=True)


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

        result = await bot.ensure_application_emoji("test_emoji", b"fake_image_bytes")

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

        result = await bot.ensure_application_emoji("test_emoji", b"fake_image_bytes")

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

        await bot.ensure_application_emojis()

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
            "create_application_emoji",
            AsyncMock(side_effect=mock_emojis),
        )

        await bot.ensure_application_emojis()

        # Should have called create_application_emoji for each emoji file
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
        await bot.ensure_application_emojis()


class TestTTLDict:
    def test_evicts_oldest_when_maxsize_exceeded(self) -> None:
        cache = TTLDict[int, str](maxsize=2, ttl=3600)
        cache[1] = "a"
        cache[2] = "b"
        cache[3] = "c"
        assert cache.get(1) is None
        assert cache[2] == "b"
        assert cache[3] == "c"

    def test_purge_removes_expired_entries(self, mocker: MockerFixture) -> None:
        now = mocker.patch("spellbot.client.monotonic", return_value=1000.0)
        cache = TTLDict[int, str](maxsize=10, ttl=60.0)
        cache[1] = "a"
        cache[2] = "b"
        now.return_value = 2000.0
        assert cache.get(1) is None
        assert cache.get(2) is None
