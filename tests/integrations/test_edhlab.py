from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.edhlab as edhlab_module
from spellbot.enums import GameBracket
from spellbot.integrations.edhlab import fetch_edhlab_link, generate_link
from tests.mocks import create_mock_game


class TestFetchEdhlabLink:
    @pytest.mark.asyncio
    async def test_fetch_edhlab_link_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"gameUrl": "https://edhlab.gg/game/123"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=42,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_api_key"),
            patch.object(
                edhlab_module.settings,
                "EDHLAB_CREATE",
                "https://api.edhlab.gg/create-game",
            ),
        ):
            result = await fetch_edhlab_link(mock_client, game)

        assert result == {"gameUrl": "https://edhlab.gg/game/123"}
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        # No bracket when NONE
        assert "bracket" not in payload

    @pytest.mark.asyncio
    async def test_fetch_edhlab_link_with_bracket(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"gameUrl": "https://edhlab.gg/game/456"}
        mock_client.post = AsyncMock(return_value=mock_response)

        game = create_mock_game(
            game_id=99,
            bracket=GameBracket.BRACKET_2.value,
        )

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_api_key"),
            patch.object(
                edhlab_module.settings,
                "EDHLAB_CREATE",
                "https://api.edhlab.gg/create-game",
            ),
        ):
            result = await fetch_edhlab_link(mock_client, game)

        assert result == {"gameUrl": "https://edhlab.gg/game/456"}
        payload = mock_client.post.call_args.kwargs["json"]
        # BRACKET_2.value (3) -> bracket = 3 - 1 = 2
        assert payload["bracket"] == 2


class TestGenerateLink:
    @pytest.mark.asyncio
    async def test_generate_link_no_api_key(self) -> None:
        game = create_mock_game(game_id=1)

        with patch.object(edhlab_module.settings, "EDHLAB_API_KEY", ""):
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_success(self) -> None:
        game = create_mock_game(
            game_id=1,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_key"),
            patch.object(
                edhlab_module,
                "fetch_edhlab_link",
                AsyncMock(return_value={"gameUrl": "https://edhlab.gg/game/123"}),
            ),
        ):
            result = await generate_link(game)

        assert result == ("https://edhlab.gg/game/123", None)

    @pytest.mark.asyncio
    async def test_generate_link_retries_on_failure_then_succeeds(self) -> None:
        """Test that generate_link retries after failure and succeeds on second attempt."""
        game = create_mock_game(
            game_id=1,
            bracket=GameBracket.NONE.value,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"gameUrl": "https://edhlab.gg/game/789"}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[Exception("Connection error"), mock_response],
        )

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_key"),
            patch.object(
                edhlab_module.settings,
                "EDHLAB_CREATE",
                "https://api.edhlab.gg/create-game",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(edhlab_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == ("https://edhlab.gg/game/789", None)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_link_fails_after_all_retries(self) -> None:
        """Test that generate_link returns None after exhausting all retry attempts."""
        game = create_mock_game(
            game_id=1,
            bracket=GameBracket.NONE.value,
        )

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_key"),
            patch.object(
                edhlab_module.settings,
                "EDHLAB_CREATE",
                "https://api.edhlab.gg/create-game",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(edhlab_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == (None, None)
        assert mock_client.post.call_count == edhlab_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_generate_link_returns_none_when_data_is_empty(self) -> None:
        """Test that generate_link returns None when fetch_edhlab_link returns empty dict."""
        game = create_mock_game(
            game_id=1,
            bracket=GameBracket.NONE.value,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_key"),
            patch.object(
                edhlab_module.settings,
                "EDHLAB_CREATE",
                "https://api.edhlab.gg/create-game",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await generate_link(game)

        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_generate_link_zero_retry_attempts(self) -> None:
        """Test that generate_link returns None when RETRY_ATTEMPTS is 0."""
        game = create_mock_game(
            game_id=1,
            bracket=GameBracket.NONE.value,
        )

        with (
            patch.object(edhlab_module.settings, "EDHLAB_API_KEY", "test_key"),
            patch.object(edhlab_module, "RETRY_ATTEMPTS", 0),
        ):
            result = await generate_link(game)

        assert result == (None, None)
