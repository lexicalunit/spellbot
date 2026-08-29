# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import spellbot.integrations.castlog as castlog_module
from spellbot.integrations.castlog import fetch_castlog_report, report_match


class TestFetchCastlogReport:
    @pytest.mark.asyncio
    async def test_fetch_castlog_report_success(self) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "match_id": "abc-123",
            "castlog_url": "https://app.castlog.gg/match/abc-123",
            "linked_players": ["ravepool"],
            "unlinked_players": [],
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        payload = {"players": [{"xid": 1, "commander": "Atraxa", "is_winner": True}]}

        with (
            patch.object(castlog_module.settings, "CASTLOG_SECRET", "test-secret"),
            patch.object(
                castlog_module.settings,
                "CASTLOG_ENDPOINT",
                "https://dev.api.castlog.gg/functions/v1/spellbot-webhook",
            ),
        ):
            result = await fetch_castlog_report(mock_client, payload)

        assert result == {
            "match_id": "abc-123",
            "castlog_url": "https://app.castlog.gg/match/abc-123",
            "linked_players": ["ravepool"],
            "unlinked_players": [],
        }
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://dev.api.castlog.gg/functions/v1/spellbot-webhook"
        assert call_args.kwargs["json"] == payload
        assert call_args.kwargs["headers"]["X-SpellBot-Secret"] == "test-secret"


class TestReportMatch:
    @pytest.mark.asyncio
    async def test_report_match_no_endpoint(self) -> None:
        with (
            patch.object(castlog_module.settings, "CASTLOG_ENDPOINT", ""),
            patch.object(castlog_module.settings, "CASTLOG_SECRET", "test-secret"),
        ):
            result = await report_match({"players": []})

        assert result is None

    @pytest.mark.asyncio
    async def test_report_match_no_secret(self) -> None:
        with (
            patch.object(
                castlog_module.settings,
                "CASTLOG_ENDPOINT",
                "https://dev.api.castlog.gg/functions/v1/spellbot-webhook",
            ),
            patch.object(castlog_module.settings, "CASTLOG_SECRET", None),
        ):
            result = await report_match({"players": []})

        assert result is None

    @pytest.mark.asyncio
    async def test_report_match_success(self) -> None:
        payload = {"players": [{"xid": 1, "commander": "Atraxa"}]}

        with (
            patch.object(castlog_module.settings, "CASTLOG_SECRET", "test-secret"),
            patch.object(
                castlog_module.settings,
                "CASTLOG_ENDPOINT",
                "https://dev.api.castlog.gg/functions/v1/spellbot-webhook",
            ),
            patch.object(
                castlog_module,
                "fetch_castlog_report",
                AsyncMock(return_value={"match_id": "abc-123"}),
            ),
        ):
            result = await report_match(payload)

        assert result == {"match_id": "abc-123"}

    @pytest.mark.asyncio
    async def test_report_match_retries_on_failure_then_succeeds(self) -> None:
        payload = {"players": []}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"match_id": "xyz-789"}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[Exception("Connection error"), mock_response],
        )

        with (
            patch.object(castlog_module.settings, "CASTLOG_SECRET", "test-secret"),
            patch.object(
                castlog_module.settings,
                "CASTLOG_ENDPOINT",
                "https://dev.api.castlog.gg/functions/v1/spellbot-webhook",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(castlog_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await report_match(payload)

        assert result == {"match_id": "xyz-789"}
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_report_match_fails_after_all_retries(self) -> None:
        payload = {"players": []}

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=Exception("Connection error"))

        with (
            patch.object(castlog_module.settings, "CASTLOG_SECRET", "test-secret"),
            patch.object(
                castlog_module.settings,
                "CASTLOG_ENDPOINT",
                "https://dev.api.castlog.gg/functions/v1/spellbot-webhook",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
            patch.object(castlog_module, "add_span_error"),
        ):
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await report_match(payload)

        assert result is None
        assert mock_client.post.call_count == castlog_module.RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_report_match_zero_retry_attempts(self) -> None:
        with (
            patch.object(castlog_module.settings, "CASTLOG_SECRET", "test-secret"),
            patch.object(
                castlog_module.settings,
                "CASTLOG_ENDPOINT",
                "https://dev.api.castlog.gg/functions/v1/spellbot-webhook",
            ),
            patch.object(castlog_module, "RETRY_ATTEMPTS", 0),
        ):
            result = await report_match({"players": []})

        assert result is None
