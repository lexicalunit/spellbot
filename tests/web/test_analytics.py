from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.settings import settings
from spellbot.utils import generate_signed_url

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohttp.client import ClientSession
    from freezegun.api import FrozenDateTimeFactory
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestWebAnalyticsShell:
    """Tests for the shell page endpoint (returns HTML immediately)."""

    async def test_analytics_shell_happy_path(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        guild = factories.guild.create(xid=201, name="test-guild")

        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        path = url.split("bot.spellbot.io")[-1]

        resp = await client.get(path)
        assert resp.status == 200
        text = await resp.text()
        assert "test-guild" in text
        assert "Loading analytics" in text

    async def test_analytics_shell_invalid_guild(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(99999, expires_in_minutes=10)
        path = url.split("bot.spellbot.io")[-1]

        resp = await client.get(path)
        assert resp.status == 404

    async def test_analytics_shell_missing_signature(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/201/analytics")
        assert resp.status == 403

    async def test_analytics_shell_expired_signature(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(201, expires_in_minutes=10)
        path = url.split("bot.spellbot.io")[-1]

        mocker.patch("spellbot.utils.time.time", return_value=2000.0)
        resp = await client.get(path)
        assert resp.status == 403

    async def test_analytics_shell_invalid_signature(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/201/analytics?expires=9999999999&sig=bad")
        assert resp.status == 403

    async def test_analytics_shell_bad_guild_in_url(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/notanumber/analytics?expires=9999999999&sig=bad")
        assert resp.status == 404


@pytest.mark.asyncio
class TestWebAnalyticsSummary:
    """Tests for the summary endpoint (returns JSON with summary stats)."""

    async def test_analytics_summary_happy_path(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        guild = factories.guild.create(xid=201, name="test-guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        user = factories.user.create(xid=101, name="player1")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=datetime.now(tz=UTC),
            created_at=datetime.now(tz=UTC),
        )
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        data_path = (
            f"/g/{guild.xid}/analytics/summary?expires={query['expires'][0]}&sig={query['sig'][0]}"
        )

        resp = await client.get(data_path)
        assert resp.status == 200
        data = await resp.json()
        assert data["total_games"] == 1
        assert data["active_players"] == 1

    async def test_analytics_summary_invalid_guild(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(99999, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        path = f"/g/99999/analytics/summary?expires={query['expires'][0]}&sig={query['sig'][0]}"

        resp = await client.get(path)
        assert resp.status == 404

    async def test_analytics_summary_missing_signature(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/201/analytics/summary")
        assert resp.status == 403

    async def test_analytics_summary_expired_signature(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(201, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        path = f"/g/201/analytics/summary?expires={query['expires'][0]}&sig={query['sig'][0]}"

        mocker.patch("spellbot.utils.time.time", return_value=2000.0)
        resp = await client.get(path)
        assert resp.status == 403

    async def test_analytics_summary_invalid_signature(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/201/analytics/summary?expires=9999999999&sig=bad")
        assert resp.status == 403

    async def test_analytics_summary_bad_guild_in_url(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/notanumber/analytics/summary?expires=9999999999&sig=bad")
        assert resp.status == 404


@pytest.mark.asyncio
class TestWebAnalyticsEndpoints:
    """Tests for all analytics JSON endpoints."""

    async def _get_analytics_endpoint(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
        endpoint: str,
    ) -> dict[str, object]:
        guild = factories.guild.create(xid=201, name="test-guild")
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/{endpoint}?expires={expires}&sig={sig}"
        resp = await client.get(path)
        assert resp.status == 200
        return await resp.json()

    async def test_analytics_wait_time(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "wait-time")
        assert "avg_wait_per_day" in data

    async def test_analytics_brackets(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "brackets")
        assert "games_by_bracket_per_day" in data

    async def test_analytics_retention(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "retention")
        assert "player_retention" in data

    async def test_analytics_growth(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "growth")
        assert "cumulative_players" in data

    async def test_analytics_formats(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "formats")
        assert "popular_formats" in data

    async def test_analytics_services(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "services")
        assert "popular_services" in data

    async def test_analytics_players(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "players")
        assert "top_players" in data

    async def test_analytics_blocked(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "blocked")
        assert "top_blocked" in data

    async def test_analytics_activity(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "activity")
        assert "games_per_day" in data

    async def test_analytics_histogram(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "histogram")
        assert "games_histogram" in data

    async def test_analytics_channels(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self._get_analytics_endpoint(client, factories, mocker, "channels")
        assert "busiest_channels" in data


@pytest.mark.asyncio
class TestWebAnalyticsSignatureBypass:
    """Tests for CHECK_SIGNATURE=False bypass."""

    async def test_analytics_summary_without_signature_when_check_disabled(
        self,
        aiohttp_client: Callable[..., Awaitable[ClientSession]],
        factories: Factories,
    ) -> None:
        """When CHECK_SIGNATURE is False, requests without sig params should succeed."""
        from spellbot.web import build_web_app  # allow_inline

        guild = factories.guild.create(xid=202, name="bypass-guild")

        # Temporarily disable signature checking BEFORE creating the app/client
        original_value = settings.CHECK_SIGNATURE
        object.__setattr__(settings, "CHECK_SIGNATURE", False)

        try:
            # Create a new client with settings already disabled
            app = build_web_app()
            test_client = await aiohttp_client(app)

            # Request the summary JSON endpoint without any signature parameters
            path = f"/g/{guild.xid}/analytics/summary"
            resp = await test_client.get(path)
            assert resp.status == 200
            data = await resp.json()
            assert "total_games" in data
        finally:
            object.__setattr__(settings, "CHECK_SIGNATURE", original_value)
