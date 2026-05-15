from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.tablestream as tablestream_module
from spellbot.enums import GameFormat
from spellbot.integrations.tablestream import (
    TableStreamGameTypes,
    build_ts_args,
    fetch_table_stream_link,
    generate_link,
    table_stream_game_type,
)
from tests.mocks import create_mock_game


class TestTableStreamGameType:
    def test_commander_formats(self) -> None:
        commander_formats = [
            GameFormat.COMMANDER,
            GameFormat.OATHBREAKER,
            GameFormat.BRAWL_MULTIPLAYER,
            GameFormat.EDH_MAX,
            GameFormat.EDH_HIGH,
            GameFormat.EDH_MID,
            GameFormat.EDH_LOW,
            GameFormat.EDH_BATTLECRUISER,
            GameFormat.PLANECHASE,
            GameFormat.TWO_HEADED_GIANT,
            GameFormat.PRE_CONS,
            GameFormat.CEDH,
            GameFormat.PAUPER_EDH,
            GameFormat.ARCHENEMY,
            GameFormat.HORDE_MAGIC,
        ]
        for fmt in commander_formats:
            assert table_stream_game_type(fmt) == TableStreamGameTypes.MTGCommander

    def test_legacy_formats(self) -> None:
        legacy_formats = [
            GameFormat.LEGACY,
            GameFormat.PAUPER,
            GameFormat.DUEL_COMMANDER,
            GameFormat.BRAWL_TWO_PLAYER,
        ]
        for fmt in legacy_formats:
            assert table_stream_game_type(fmt) == TableStreamGameTypes.MTGLegacy

    def test_modern_formats(self) -> None:
        modern_formats = [GameFormat.MODERN, GameFormat.PIONEER]
        for fmt in modern_formats:
            assert table_stream_game_type(fmt) == TableStreamGameTypes.MTGModern

    def test_standard_formats(self) -> None:
        standard_formats = [GameFormat.STANDARD, GameFormat.SEALED]
        for fmt in standard_formats:
            assert table_stream_game_type(fmt) == TableStreamGameTypes.MTGStandard

    def test_vintage_format(self) -> None:
        assert table_stream_game_type(GameFormat.VINTAGE) == TableStreamGameTypes.MTGVintage


class TestBuildTsArgs:
    def test_build_ts_args_commander(self) -> None:
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)
        args = build_ts_args(game)

        assert args["roomName"] == "SB42"
        assert args["gameType"] == "MTGCommander"
        assert args["maxPlayers"] == 4
        assert args.get("private") is True
        assert args.get("initialScheduleTTLInSeconds") == 3600

    def test_build_ts_args_legacy(self) -> None:
        game = create_mock_game(game_id=123, game_format=GameFormat.LEGACY.value)
        args = build_ts_args(game)

        assert args["roomName"] == "SB123"
        assert args["gameType"] == "MTGLegacy"


class TestFetchTableStreamLink:
    @pytest.mark.asyncio
    async def test_fetch_table_stream_link_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "room": {
                "roomName": "SB42",
                "roomId": "test-uuid",
                "roomUrl": "https://table-stream.com/game?id=test-uuid",
                "gameType": "MTGCommander",
                "maxPlayers": 4,
                "password": "secret123",
            },
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        # Use build_ts_args to create a properly typed TableStreamArgs
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)
        ts_args = build_ts_args(game)

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_auth_key"),
            patch.object(
                tablestream_module.settings,
                "TABLESTREAM_CREATE",
                "https://api.table-stream.com/create-room",
            ),
        ):
            result = await fetch_table_stream_link(mock_client, ts_args)

        assert result is not None
        assert result["room"]["roomUrl"] == "https://table-stream.com/game?id=test-uuid"
        assert result["room"]["password"] == "secret123"
        mock_client.post.assert_called_once()


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_generate_link_no_auth_key(self) -> None:
        game = create_mock_game(game_id=1, game_format=GameFormat.COMMANDER.value)

        with patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", ""):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_none_auth_key(self) -> None:
        game = create_mock_game(game_id=1, game_format=GameFormat.COMMANDER.value)

        with patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", None):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_success(self) -> None:
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_key"),
            patch.object(
                tablestream_module,
                "fetch_table_stream_link",
                AsyncMock(
                    return_value={
                        "room": {
                            "roomUrl": "https://table-stream.com/game?id=test-uuid",
                            "password": "secret123",
                        },
                    },
                ),
            ),
        ):
            result = await generate_link(game)

        assert result == ("https://table-stream.com/game?id=test-uuid", "secret123")

    @pytest.mark.asyncio
    async def test_generate_link_retries_on_failure_then_succeeds(self) -> None:
        """Test that generate_link retries after failure and succeeds on second attempt."""
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "room": {
                "roomUrl": "https://table-stream.com/game?id=retry-uuid",
                "password": "retry123",
            },
        }

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[Exception("Connection error"), mock_response],
        )

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_key"),
            patch.object(
                tablestream_module.settings,
                "TABLESTREAM_CREATE",
                "https://api.table-stream.com/create-room",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(tablestream_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == ("https://table-stream.com/game?id=retry-uuid", "retry123")
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_link_fails_after_all_retries(self) -> None:
        """Test that generate_link returns None after exhausting all retry attempts."""
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_key"),
            patch.object(
                tablestream_module.settings,
                "TABLESTREAM_CREATE",
                "https://api.table-stream.com/create-room",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(tablestream_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == (None, None)
        assert mock_client.post.call_count == tablestream_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_generate_link_returns_none_when_data_is_none(self) -> None:
        """Test that generate_link returns None when fetch returns None."""
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_key"),
            patch.object(
                tablestream_module,
                "fetch_table_stream_link",
                AsyncMock(return_value=None),
            ),
        ):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_returns_none_when_room_missing(self) -> None:
        """Test that generate_link returns None when room data is missing."""
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_key"),
            patch.object(
                tablestream_module,
                "fetch_table_stream_link",
                AsyncMock(return_value={}),
            ),
        ):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_zero_retry_attempts(self) -> None:
        """Test that generate_link returns None when RETRY_ATTEMPTS is 0."""
        game = create_mock_game(game_id=42, game_format=GameFormat.COMMANDER.value)

        with (
            patch.object(tablestream_module.settings, "TABLESTREAM_AUTH_KEY", "test_key"),
            patch.object(tablestream_module, "RETRY_ATTEMPTS", 0),
        ):
            result = await generate_link(game)

        assert result == (None, None)
