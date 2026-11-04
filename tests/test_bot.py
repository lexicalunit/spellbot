# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
import httpx
import pytest
from discord import app_commands
from discord.ext.commands import (
    AutoShardedBot,
    CommandError,
    CommandNotFound,
    Context,
    UserInputError,
)

from spellbot import SpellBot, client
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
)
from spellbot.models import Game
from spellbot.utils import handle_interaction_errors
from tests.mocks import create_mock_game, decoys
from tests.mocks.decoys import ANY
from tests.mocks.http import raising, serve_httpx

if TYPE_CHECKING:
    from decoy import Decoy

    from tests.fixtures import Factories, Stub

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
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game = create_mock_game(service=service)
        bot.mock_games = mock_games
        link = GameLinkDetails("https://example.com/link")
        if factory:
            module, name = factory.split(".")
            generate_link = stub(getattr(client, module), name)
            if factory in ("convoke.generate_link", "playgroup_live.generate_link"):
                decoy.when(await generate_link(game, None)).then_return(link)
            else:
                decoy.when(await generate_link(game)).then_return(link)
        response = await bot.create_game_link(game)
        if factory:
            assert response == link
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
            pytest.param(False, GameService.GIRUDO.value, False, id="other-service"),
        ],
    )
    async def test_update_game_players(
        self,
        bot: SpellBot,
        mock_games: bool,
        service: int,
        expected: bool,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game = create_mock_game(service=service)
        bot.mock_games = mock_games
        mock = stub(client.convoke, "update_players")
        await bot.update_game_players(game, {1: "123456"})
        if expected:
            decoy.verify(await mock(game, {1: "123456"}), times=1)
        else:
            decoy.verify(await mock(game_data=ANY, pins=ANY), times=0, ignore_extra_args=True)

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

    async def test_handle_interaction_errors_names_the_command(
        self,
        interaction: discord.Interaction,
        caplog: pytest.LogCaptureFixture,
        decoy: Decoy,
    ) -> None:
        command = decoy.mock(cls=app_commands.Command)
        decoy.when(command.qualified_name).then_return("lfg")
        interaction.command = command
        await handle_interaction_errors(interaction, RuntimeError("boom"))
        assert "unhandled exception in command `lfg`" in caplog.text

    async def test_on_message_delete_happy_path(
        self,
        decoy_message: discord.Message,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        handle_message_deleted = stub(bot, "handle_message_deleted")
        await bot.on_message_delete(decoy_message)
        decoy.verify(await handle_message_deleted(decoy_message), times=1)

    async def test_on_message_delete_message_without_id(
        self,
        decoy_message: discord.Message,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # No usable id (`on_message_delete` treats a missing id and a zero id alike).
        decoy_message.id = 0
        handle_message_deleted = stub(bot, "handle_message_deleted")
        await bot.on_message_delete(decoy_message)
        decoy.verify(await handle_message_deleted(ANY), times=0)

    async def test_on_command_error_command_not_found(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        context = decoy.mock(cls=Context)
        handled = record_base_command_errors(monkeypatch)
        await bot.on_command_error(context, CommandNotFound())
        assert handled == []

    async def test_on_command_error_user_input_error(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
        decoy: Decoy,
    ) -> None:
        context = decoy.mock(cls=Context)
        exception = UserInputError()
        handled = record_base_command_errors(monkeypatch)
        await bot.on_command_error(context, exception)
        assert handled == [(context, exception)]

    async def test_handle_message_deleted_when_game_not_started(
        self,
        decoy_message: discord.Message,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        assert decoy_message.guild
        guild = factories.guild.create(xid=decoy_message.guild.id)
        channel = factories.channel.create(guild=guild, xid=decoy_message.channel.id)
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
            message_xid=decoy_message.id,
        )
        await bot.handle_message_deleted(decoy_message)

        DatabaseSession.expire_all()
        refreshed = await DatabaseSession.get(Game, game.id)
        assert refreshed is not None
        assert refreshed.deleted_at is not None

    async def test_handle_message_deleted_when_game_is_started(
        self,
        decoy_message: discord.Message,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        assert decoy_message.guild
        guild = factories.guild.create(xid=decoy_message.guild.id)
        channel = factories.channel.create(guild=guild, xid=decoy_message.channel.id)
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
            message_xid=decoy_message.id,
        )
        await bot.handle_message_deleted(decoy_message)

        DatabaseSession.expire_all()
        assert game.deleted_at is None

    async def test_handle_message_deleted_when_message_not_found(
        self,
        decoy_message: discord.Message,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        assert decoy_message.guild
        guild = factories.guild.create(xid=decoy_message.guild.id)
        channel = factories.channel.create(guild=guild, xid=decoy_message.channel.id)
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
            message_xid=decoy_message.id + 1,
        )
        await bot.handle_message_deleted(decoy_message)

        DatabaseSession.expire_all()
        assert game.deleted_at is None


def record_base_command_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Context[SpellBot], CommandError]]:
    """Record what reaches discord.py's own `on_command_error`, in place of its handling."""
    handled: list[tuple[Context[SpellBot], CommandError]] = []

    async def on_command_error(
        bot: SpellBot,
        context: Context[SpellBot],
        exception: CommandError,
    ) -> None:
        handled.append((context, exception))

    monkeypatch.setattr(AutoShardedBot, "on_command_error", on_command_error)
    return handled


@pytest.mark.asyncio
class TestSpellBotEmojis:
    async def test_create_application_emoji_success(
        self,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test successful creation of application emoji."""
        mock_emoji = decoys.emoji(decoy, "test_emoji")
        create_emoji_stub = stub(bot, "create_application_emoji")
        decoy.when(
            await create_emoji_stub(name=ANY, image=ANY),
            ignore_extra_args=True,
        ).then_return(mock_emoji)

        result = await bot.ensure_application_emoji("test_emoji", b"fake_image_bytes")

        assert result == mock_emoji
        decoy.verify(await create_emoji_stub(name="test_emoji", image=b"fake_image_bytes"), times=1)

    async def test_create_application_emoji_exception(
        self,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test exception handling in create_application_emoji."""
        create_application_emoji_fake = stub(bot, "create_application_emoji")
        decoy.when(
            await create_application_emoji_fake(name=ANY, image=ANY),
            ignore_extra_args=True,
        ).then_raise(Exception("Discord API error"))

        result = await bot.ensure_application_emoji("test_emoji", b"fake_image_bytes")

        assert result is None

    async def test_ensure_application_emojis_success(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successful fetching and caching of application emojis when all emojis exist."""
        emoji_dir = ASSETS_DIR / "emoji"
        emoji_files = list(emoji_dir.glob("*.png"))
        emoji_names = [f.stem for f in emoji_files]

        items = [{"name": name, "id": str(i)} for i, name in enumerate(emoji_names)]
        serve_httpx(monkeypatch, lambda _: httpx.Response(200, json={"items": items}))

        await bot.ensure_application_emojis()

        assert len(bot.emojis_cache) == len(emoji_names)

    async def test_ensure_application_emojis_creates_missing(
        self,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that missing emojis are created."""
        emoji_dir = ASSETS_DIR / "emoji"
        emoji_files = list(emoji_dir.glob("*.png"))
        num_emojis = len(emoji_files)

        # No existing emojis
        serve_httpx(monkeypatch, lambda _: httpx.Response(200, json={"items": []}))

        # Each one is created from its file
        create_stub = stub(bot, "create_application_emoji")
        for i, f in enumerate(emoji_files):
            decoy.when(await create_stub(name=f.stem, image=f.read_bytes())).then_return(
                decoys.emoji(decoy, f.stem, emoji_id=i + 1),
            )

        await bot.ensure_application_emojis()

        # All emojis should be in the cache
        assert len(bot.emojis_cache) == num_emojis

    async def test_ensure_application_emojis_exception(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test exception handling in ensure_application_emojis."""
        serve_httpx(monkeypatch, raising())

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

    def test_purge_removes_expired_entries(self, decoy: Decoy, stub: Stub) -> None:
        now = stub(client, "monotonic")
        decoy.when(now()).then_return(1000.0)
        cache = TTLDict[int, str](maxsize=10, ttl=60.0)
        cache[1] = "a"
        cache[2] = "b"
        decoy.when(now()).then_return(2000.0)
        assert cache.get(1) is None
        assert cache.get(2) is None
