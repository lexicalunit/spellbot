from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.settings import settings
from spellbot.utils import generate_signed_url
from spellbot.web.api.analytics import check_guild_member

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

    async def get_analytics_endpoint(
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
        data = await self.get_analytics_endpoint(client, factories, mocker, "wait-time")
        assert "avg_wait_per_day" in data

    async def test_analytics_brackets(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "brackets")
        assert "games_by_bracket_per_day" in data

    async def test_analytics_retention(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "retention")
        assert "player_retention" in data

    async def test_analytics_growth(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "growth")
        assert "cumulative_players" in data

    async def test_analytics_formats(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "formats")
        assert "popular_formats" in data

    async def test_analytics_services(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "services")
        assert "popular_services" in data

    async def test_analytics_players(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        # Create a guild and player data
        guild = factories.guild.create(xid=201, name="test-guild")
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        user = factories.user.create(xid=5001, name="active-user", game=game)
        factories.guild_member.create(guild_xid=guild.xid, user_xid=user.xid)

        # Mock check_guild_member to return True (user is still a member)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            return_value=True,
        )
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/players?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 200
        data = await resp.json()
        assert "top_players" in data
        assert len(data["top_players"]) == 1
        assert data["top_players"][0]["left_server"] is False

    async def test_analytics_blocked(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        # Create a guild and blocked user data
        guild = factories.guild.create(xid=202, name="test-guild")
        blocker = factories.user.create(xid=6001, name="blocker")
        blocked = factories.user.create(xid=6002, name="blocked-user")
        factories.guild_member.create(guild_xid=guild.xid, user_xid=blocked.xid)
        factories.block.create(user_xid=blocker.xid, blocked_user_xid=blocked.xid)

        # Mock check_guild_member to return True (user is still a member)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            return_value=True,
        )
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/blocked?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 200
        data = await resp.json()
        assert "top_blocked" in data
        assert len(data["top_blocked"]) == 1
        assert data["top_blocked"][0]["left_server"] is False

    async def test_analytics_activity(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "activity")
        assert "games_per_day" in data

    async def test_analytics_histogram(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "histogram")
        assert "games_histogram" in data

    async def test_analytics_channels(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "channels")
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


@pytest.mark.asyncio
class TestWebAnalyticsMembershipChecks:
    """Tests for guild membership checking in analytics endpoints."""

    async def test_analytics_players_with_left_server(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """Test that players who left the server are marked with left_server=True."""
        guild = factories.guild.create(xid=301, name="test-guild")
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            started_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        # Create user associated with the game (this creates the Play record)
        user = factories.user.create(xid=1001, name="left-user", game=game)
        factories.guild_member.create(guild_xid=guild.xid, user_xid=user.xid)

        # Mock check_guild_member to return False (user has left)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            return_value=False,
        )
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/players?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 200
        data = await resp.json()
        assert "top_players" in data
        assert len(data["top_players"]) == 1
        assert data["top_players"][0]["left_server"] is True

    async def test_analytics_blocked_with_left_server(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """Test that blocked users who left the server are marked with left_server=True."""
        guild = factories.guild.create(xid=302, name="test-guild")
        blocker = factories.user.create(xid=2001, name="blocker")
        blocked = factories.user.create(xid=2002, name="blocked-user")
        factories.guild_member.create(guild_xid=guild.xid, user_xid=blocked.xid)
        factories.block.create(user_xid=blocker.xid, blocked_user_xid=blocked.xid)

        # Mock check_guild_member to return False (user has left)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            return_value=False,
        )
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/blocked?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 200
        data = await resp.json()
        assert "top_blocked" in data
        assert len(data["top_blocked"]) == 1
        assert data["top_blocked"][0]["left_server"] is True

    async def testcheck_guild_member_api_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that check_guild_member returns None on API errors."""
        # Mock httpx to raise an exception
        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.get = mocker.AsyncMock(side_effect=Exception("Network error"))
        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        result = await check_guild_member(12345, 67890)
        assert result is None

    async def testcheck_guild_member_success(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that check_guild_member returns True when user is a member."""
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        result = await check_guild_member(12345, 67890)
        assert result is True

    async def testcheck_guild_member_not_found(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that check_guild_member returns False when user is not a member."""
        mock_response = mocker.MagicMock()
        mock_response.status_code = 404
        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        result = await check_guild_member(12345, 67890)
        assert result is False

    async def testcheck_guild_member_rate_limited(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that check_guild_member returns None on rate limit (429)."""
        mock_response = mocker.MagicMock()
        mock_response.status_code = 429
        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.get = mocker.AsyncMock(return_value=mock_response)
        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        result = await check_guild_member(12345, 67890)
        assert result is None

    async def test_analytics_players_invalid_signature(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """Test that analytics_players returns error for invalid signature."""
        guild = factories.guild.create(xid=401, name="test-guild")
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        # Use invalid signature
        path = f"/g/{guild.xid}/analytics/players?expires=2000&sig=invalid"
        resp = await client.get(path)
        assert resp.status == 403

    async def test_analytics_players_guild_not_found(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        """Test that analytics_players returns 404 for non-existent guild."""
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        # Use a guild xid that doesn't exist in the database
        url = generate_signed_url(99999, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/99999/analytics/players?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 404

    async def test_analytics_blocked_invalid_signature(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """Test that analytics_blocked returns error for invalid signature."""
        guild = factories.guild.create(xid=402, name="test-guild")
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        # Use invalid signature
        path = f"/g/{guild.xid}/analytics/blocked?expires=2000&sig=invalid"
        resp = await client.get(path)
        assert resp.status == 403

    async def test_analytics_blocked_guild_not_found(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        """Test that analytics_blocked returns 404 for non-existent guild."""
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        # Use a guild xid that doesn't exist in the database
        url = generate_signed_url(99998, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/99998/analytics/blocked?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 404

    async def test_analytics_players_empty_results(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """Test analytics_players with no player data (empty top_players)."""
        guild = factories.guild.create(xid=403, name="empty-guild")
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/players?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 200
        data = await resp.json()
        assert data["top_players"] == []

    async def test_analytics_blocked_empty_results(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """Test analytics_blocked with no blocked user data (empty top_blocked)."""
        guild = factories.guild.create(xid=404, name="empty-guild")
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)

        url = generate_signed_url(guild.xid, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        expires = query["expires"][0]
        sig = query["sig"][0]
        path = f"/g/{guild.xid}/analytics/blocked?expires={expires}&sig={sig}"

        resp = await client.get(path)
        assert resp.status == 200
        data = await resp.json()
        assert data["top_blocked"] == []
