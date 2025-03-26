from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.client_exceptions import ClientError

from spellbot import spelltable
from spellbot.settings import Settings
from spellbot.spelltable import generate_spelltable_link_api as generate_link

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiohttp_retry.client import RetryClient


@pytest.mark.asyncio
class TestSpellTable:
    async def test_generate_link(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = MagicMock(spec=Settings)
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "settings", settings)

        mock_response = MagicMock()
        game_url = "https://game"
        mock_response.read = AsyncMock(
            return_value=b'{"gameUrl": "' + game_url.encode() + b'" }',
        )

        class MockClient:
            @asynccontextmanager
            async def post(self, *args: Any, **kwargs: Any):
                yield mock_response

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args: Any, **kwargs: Any) -> AsyncGenerator[RetryClient, None]:
            yield cast("RetryClient", mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link(MagicMock()) == game_url

    async def test_generate_link_upstream_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = MagicMock(spec=Settings)
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "settings", settings)

        mock_response = MagicMock()
        mock_response.read = AsyncMock(return_value=b"upstream request timeout")

        class MockClient:
            @asynccontextmanager
            async def post(self, *args: Any, **kwargs: Any):
                yield mock_response

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args: Any, **kwargs: Any) -> AsyncGenerator[RetryClient, None]:
            yield cast("RetryClient", mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link(MagicMock()) is None

    async def test_generate_link_missing_game_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = MagicMock(spec=Settings)
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "settings", settings)

        mock_response = MagicMock()
        mock_response.read = AsyncMock(return_value=b'{"error": 123}')

        class MockClient:
            @asynccontextmanager
            async def post(self, *args: Any, **kwargs: Any):
                yield mock_response

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args: Any, **kwargs: Any) -> AsyncGenerator[RetryClient, None]:
            yield cast("RetryClient", mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link(MagicMock()) is None

    async def test_generate_link_non_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = MagicMock(spec=Settings)
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "settings", settings)

        mock_response = MagicMock()
        mock_response.read = AsyncMock(return_value=b"foobar")

        class MockClient:
            @asynccontextmanager
            async def post(self, *args: Any, **kwargs: Any):
                yield mock_response

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[RetryClient, None]:
            yield cast("RetryClient", mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link(MagicMock()) is None

    async def test_generate_link_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = MagicMock(spec=Settings)
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "settings", settings)

        class MockClient:  # pragma: no cover
            @asynccontextmanager
            async def post(self, *args: Any, **kwargs: Any):
                raise ClientError

                # Need to yield to satisfy static analysis of @asynccontextmanager.
                yield

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args: Any, **kwargs: Any) -> AsyncGenerator[RetryClient, None]:
            yield cast("RetryClient", mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link(MagicMock()) is None
