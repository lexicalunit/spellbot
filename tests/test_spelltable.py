from contextlib import asynccontextmanager
from typing import AsyncGenerator, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.client_exceptions import ClientError
from aiohttp_retry.client import RetryClient

from spellbot import spelltable
from spellbot.spelltable import generate_link


@pytest.mark.asyncio
class TestSpellTable:
    async def test_generate_link(self, monkeypatch):
        settings = MagicMock()
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "Settings", lambda: settings)

        mock_response = MagicMock()
        game_url = "https://game"
        mock_response.json = AsyncMock(return_value={"gameUrl": game_url})

        class MockClient:
            @asynccontextmanager
            async def post(*args, **kwargs):
                yield mock_response

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args, **kwargs) -> AsyncGenerator[RetryClient, None]:
            yield cast(RetryClient, mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link() == game_url

    async def test_generate_link_missing_game_url(self, monkeypatch):
        settings = MagicMock()
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "Settings", lambda: settings)

        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"error": 123})

        class MockClient:
            @asynccontextmanager
            async def post(*args, **kwargs):
                yield mock_response

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args, **kwargs) -> AsyncGenerator[RetryClient, None]:
            yield cast(RetryClient, mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link() is None

    async def test_generate_link_raises_error(self, monkeypatch):
        settings = MagicMock()
        settings.SPELLTABLE_AUTH_KEY = "auth-key"
        settings.SPELLTABLE_CREATE = "https://create"
        monkeypatch.setattr(spelltable, "Settings", lambda: settings)

        class MockClient:
            @asynccontextmanager
            async def post(*args, **kwargs):
                raise ClientError()

                # Need to yield to satisfy static analysis of @asynccontextmanager.
                yield  # noqa

        mock_client = MockClient()

        @asynccontextmanager
        async def MockRetryClient(*args, **kwargs) -> AsyncGenerator[RetryClient, None]:
            yield cast(RetryClient, mock_client)

        monkeypatch.setattr(spelltable, "RetryClient", MockRetryClient)

        assert await generate_link() is None
