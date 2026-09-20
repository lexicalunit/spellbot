# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.settings import settings
from spellbot.utils import generate_signed_url
from spellbot.web.api import analytics
from spellbot.web.api.analytics import Membership, check_guild_member

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
        parsed = urlparse(url)
        path = f"{parsed.path}?{parsed.query}"

        resp = await client.get(path)
        assert resp.status == 200
        text = await resp.text()
        assert "test-guild" in text
        assert "Loading analytics" in text
        # The page links back to the guild page.
        assert f'href="/g/{guild.xid}"' in text

    async def test_analytics_shell_invalid_guild(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(99999, expires_in_minutes=10)
        parsed = urlparse(url)
        path = f"{parsed.path}?{parsed.query}"

        resp = await client.get(path)
        assert resp.status == 404

    async def test_analytics_shell_anonymous_redirected_to_login(
        self,
        client: ClientSession,
    ) -> None:
        # No signature and no logged-in session: bounce to login like the settings/audit pages.
        resp = await client.get("/g/201/analytics", allow_redirects=False)
        assert resp.status == 302
        assert "/login" in resp.headers["Location"]

    async def test_analytics_shell_expired_signature_redirected_to_login(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(201, expires_in_minutes=10)
        parsed = urlparse(url)
        path = f"{parsed.path}?{parsed.query}"

        mocker.patch("spellbot.utils.time.time", return_value=2000.0)
        resp = await client.get(path, allow_redirects=False)
        assert resp.status == 302
        assert "/login" in resp.headers["Location"]

    async def test_analytics_shell_invalid_signature_redirected_to_login(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get(
            "/g/201/analytics?expires=9999999999&sig=bad",
            allow_redirects=False,
        )
        assert resp.status == 302
        assert "/login" in resp.headers["Location"]

    async def test_analytics_shell_logged_in_non_moderator_forbidden(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        factories.guild.create(xid=201, name="test-guild")
        resp = await owner_client.get("/g/201/analytics")
        assert resp.status == 403

    async def test_analytics_shell_moderator_session(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        # A logged-in moderator can view analytics without a signed link.
        factories.guild.create(xid=201, name="test-guild")
        resp = await mod_client.get("/g/201/analytics")
        assert resp.status == 200
        text = await resp.text()
        assert "test-guild" in text
        # Session view shows the Share button (not the expiry countdown).
        assert "Share this page" in text
        # The page links back to the guild page.
        assert 'href="/g/201"' in text

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

    async def test_analytics_summary_moderator_session(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        # A logged-in moderator can fetch analytics data without a signed link.
        # NB: don't freeze/mock time here — that patches the global `time.time` and
        # breaks the encrypted session cookie, dropping the moderator's session.
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

        resp = await mod_client.get(f"/g/{guild.xid}/analytics/summary")
        assert resp.status == 200
        data = await resp.json()
        assert data["total_games"] == 1

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

    async def test_analytics_languages(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "languages")
        assert "top_languages" in data

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
            return_value=Membership.MEMBER,
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
            return_value=Membership.MEMBER,
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

    async def test_analytics_channel_players(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "channel-players")
        assert "channel_players" in data

    async def test_analytics_hour_of_day(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "hour-of-day")
        assert "games_by_hour" in data
        games_by_hour = data["games_by_hour"]
        assert isinstance(games_by_hour, list)
        assert len(games_by_hour) == 24  # All 24 hours

    async def test_analytics_day_of_week(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "day-of-week")
        assert "games_by_day" in data
        games_by_day = data["games_by_day"]
        assert isinstance(games_by_day, list)
        assert len(games_by_day) == 7  # All 7 days

    async def test_analytics_rules(
        self,
        client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        data = await self.get_analytics_endpoint(client, factories, mocker, "rules")
        assert "top_rules" in data
        assert "rule_ngrams" in data
        top_rules = data["top_rules"]
        assert isinstance(top_rules, list)
        rule_ngrams = data["rule_ngrams"]
        assert isinstance(rule_ngrams, list)


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
            # See the `client` fixture: disable the test server's access logger to
            # dodge aiohttp's Python 3.14 access-log time-formatter crash.
            test_client = await aiohttp_client(app, server_kwargs={"access_log": None})

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
            return_value=Membership.LEFT,
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
            return_value=Membership.LEFT,
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

    @staticmethod
    def client_returning(mocker: MockerFixture, status: int) -> Any:
        response = mocker.MagicMock()
        response.status_code = status
        client = mocker.MagicMock()
        client.get = mocker.AsyncMock(return_value=response)
        return client

    async def testcheck_guild_member_api_error(
        self,
        mocker: MockerFixture,
    ) -> None:
        """A transport failure is unknown, not evidence that the user left."""
        client = mocker.MagicMock()
        client.get = mocker.AsyncMock(side_effect=Exception("Network error"))

        assert await check_guild_member(client, 12345, 67890) is Membership.UNKNOWN

    async def testcheck_guild_member_success(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that check_guild_member reports a member on 200."""
        client = self.client_returning(mocker, 200)
        assert await check_guild_member(client, 12345, 67890) is Membership.MEMBER

    async def testcheck_guild_member_not_found(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that check_guild_member reports a departure on 404."""
        client = self.client_returning(mocker, 404)
        assert await check_guild_member(client, 12345, 67890) is Membership.LEFT

    async def testcheck_guild_member_rate_limited(
        self,
        mocker: MockerFixture,
    ) -> None:
        """A 429 is reported distinctly so the caller can stop asking."""
        client = self.client_returning(mocker, 429)
        assert await check_guild_member(client, 12345, 67890) is Membership.RATE_LIMITED

    async def test_check_guild_member_unexpected_status(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Any other status is unknown rather than a departure."""
        client = self.client_returning(mocker, 500)
        assert await check_guild_member(client, 12345, 67890) is Membership.UNKNOWN

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


@pytest.mark.asyncio
class TestWebAnalyticsShare:
    """Tests for the moderator-only 'Share this page' endpoint."""

    async def test_share_moderator_returns_signed_url(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        # NB: don't mock the global clock here — it would invalidate the session cookie.
        guild = factories.guild.create(xid=201, name="test-guild")

        resp = await mod_client.get(f"/g/{guild.xid}/analytics/share")
        assert resp.status == 200
        data = await resp.json()
        # The minted link points at the analytics page and carries a signature.
        assert f"/g/{guild.xid}/analytics" in data["url"]
        assert "expires=" in data["url"]
        assert "sig=" in data["url"]

    async def test_share_anonymous_forbidden(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="test-guild")
        resp = await client.get(f"/g/{guild.xid}/analytics/share")
        assert resp.status == 403

    async def test_share_non_moderator_forbidden(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="test-guild")
        resp = await owner_client.get(f"/g/{guild.xid}/analytics/share")
        assert resp.status == 403

    async def test_share_guild_not_found(
        self,
        mod_client: ClientSession,
    ) -> None:
        resp = await mod_client.get("/g/99999/analytics/share")
        assert resp.status == 404

    async def test_share_bad_guild_in_url(
        self,
        mod_client: ClientSession,
    ) -> None:
        resp = await mod_client.get("/g/notanumber/analytics/share")
        assert resp.status == 404


@pytest.mark.asyncio
class TestWebAnalyticsDirect:
    """Direct invocation tests so coverage can track lines through aiohttp middleware."""

    async def test_analytics_json_endpoint_guild_not_found(self) -> None:
        request = MagicMock()
        request.match_info = {"guild": "99999"}
        request.query = {}
        with patch("spellbot.web.api.analytics.settings") as mock_settings:
            mock_settings.CHECK_SIGNATURE = False
            resp = await analytics.analytics_json_endpoint(request, AsyncMock(return_value={}))
            assert resp.status == 404

    async def test_analytics_json_endpoint_guild_exists(
        self,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=8001, name="g")
        request = MagicMock()
        request.match_info = {"guild": str(guild.xid)}
        request.query = {}
        with patch("spellbot.web.api.analytics.settings") as mock_settings:
            mock_settings.CHECK_SIGNATURE = False
            fetch = AsyncMock(return_value={"a": 1})
            resp = await analytics.analytics_json_endpoint(request, fetch)
            assert resp.status == 200

    async def test_analytics_endpoint_guild_not_found(self, mocker: MockerFixture) -> None:
        request = MagicMock()
        request.match_info = {"guild": "99999"}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        resp = await analytics.analytics_endpoint(request)
        assert resp.status == 404

    async def test_analytics_endpoint_happy_path(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=8002, name="g2")
        request = MagicMock()
        request.match_info = {"guild": str(guild.xid)}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        mocker.patch(
            "spellbot.web.api.analytics.aiohttp_jinja2.render_template",
            return_value="ok",
        )
        resp = await analytics.analytics_endpoint(request)
        assert resp == "ok"

    async def test_analytics_players_endpoint_guild_not_found(
        self,
        mocker: MockerFixture,
    ) -> None:
        request = MagicMock()
        request.match_info = {"guild": "99999"}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        resp = await analytics.analytics_players_endpoint(request)
        assert resp.status == 404

    async def test_analytics_players_endpoint_empty_top_players(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=8003, name="g3")
        request = MagicMock()
        request.match_info = {"guild": str(guild.xid)}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        resp = await analytics.analytics_players_endpoint(request)
        assert resp.status == 200

    async def test_analytics_blocked_endpoint_guild_not_found(
        self,
        mocker: MockerFixture,
    ) -> None:
        request = MagicMock()
        request.match_info = {"guild": "99999"}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        resp = await analytics.analytics_blocked_endpoint(request)
        assert resp.status == 404

    async def test_analytics_blocked_endpoint_empty_top_blocked(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=8004, name="g4")
        request = MagicMock()
        request.match_info = {"guild": str(guild.xid)}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        resp = await analytics.analytics_blocked_endpoint(request)
        assert resp.status == 200

    async def test_analytics_players_endpoint_with_top_players(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=8005, name="g5")
        request = MagicMock()
        request.match_info = {"guild": str(guild.xid)}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        mocker.patch(
            "spellbot.services.plays.analytics_players",
            AsyncMock(return_value={"top_players": [{"user_xid": "1"}]}),
        )
        mocker.patch(
            "spellbot.web.api.analytics.check_membership_and_update",
            AsyncMock(return_value=[{"user_xid": "1", "left_server": False}]),
        )
        resp = await analytics.analytics_players_endpoint(request)
        assert resp.status == 200

    async def test_analytics_blocked_endpoint_with_top_blocked(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=8006, name="g6")
        request = MagicMock()
        request.match_info = {"guild": str(guild.xid)}
        request.query = {"expires": "9999999999", "sig": "x"}
        mocker.patch("spellbot.web.api.analytics.validate_signature", return_value=True)
        mocker.patch(
            "spellbot.services.plays.analytics_blocked",
            AsyncMock(return_value={"top_blocked": [{"user_xid": "1"}]}),
        )
        mocker.patch(
            "spellbot.web.api.analytics.check_membership_and_update",
            AsyncMock(return_value=[{"user_xid": "1", "left_server": False}]),
        )
        resp = await analytics.analytics_blocked_endpoint(request)
        assert resp.status == 200


@pytest.mark.asyncio
class TestMembershipTTL:
    """A membership Discord already confirmed is reused instead of asked about again."""

    @staticmethod
    def players(*xids: int) -> list[dict[str, Any]]:
        return [{"user_xid": str(xid), "name": f"p{xid}", "count": 1} for xid in xids]

    async def test_recently_checked_member_is_not_refetched(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=901)
        user = factories.user.create(xid=9001)
        factories.guild_member.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            membership_checked_at=datetime.now(UTC).replace(tzinfo=None),
        )
        check = mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.MEMBER),
        )

        result = await analytics.check_membership_and_update(guild.xid, self.players(user.xid))

        check.assert_not_called()
        assert result[0]["left_server"] is False

    async def test_stale_member_is_refetched(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=902)
        user = factories.user.create(xid=9002)
        stale = datetime.now(UTC).replace(tzinfo=None) - analytics.MEMBERSHIP_TTL
        stale -= timedelta(days=1)
        factories.guild_member.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            membership_checked_at=stale,
        )
        check = mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.MEMBER),
        )

        await analytics.check_membership_and_update(guild.xid, self.players(user.xid))

        check.assert_called_once()

    async def test_never_checked_member_is_fetched(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=903)
        user = factories.user.create(xid=9003)
        factories.guild_member.create(guild_xid=guild.xid, user_xid=user.xid)
        check = mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.MEMBER),
        )

        await analytics.check_membership_and_update(guild.xid, self.players(user.xid))

        check.assert_called_once()

    async def test_confirmed_member_starts_a_fresh_ttl(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=904)
        user = factories.user.create(xid=9004)
        factories.guild_member.create(guild_xid=guild.xid, user_xid=user.xid)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.MEMBER),
        )

        await analytics.check_membership_and_update(guild.xid, self.players(user.xid))

        fresh = await analytics.recently_checked_members(guild.xid, [user.xid])
        assert fresh == {user.xid}

    async def test_rate_limit_stops_asking_for_the_rest_of_the_request(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """The whole point: one refusal must not be followed by nine more requests."""
        guild = factories.guild.create(xid=905)
        xids = list(range(9101, 9111))
        for xid in xids:
            factories.user.create(xid=xid)
            factories.guild_member.create(guild_xid=guild.xid, user_xid=xid)
        check = mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.RATE_LIMITED),
        )

        result = await analytics.check_membership_and_update(guild.xid, self.players(*xids))

        assert check.await_count == 1
        assert len(result) == len(xids)
        assert all(player["left_server"] is False for player in result)

    async def test_departure_deletes_the_record(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=906)
        user = factories.user.create(xid=9006)
        factories.guild_member.create(guild_xid=guild.xid, user_xid=user.xid)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.LEFT),
        )

        result = await analytics.check_membership_and_update(guild.xid, self.players(user.xid))

        assert result[0]["left_server"] is True
        assert await analytics.recently_checked_members(guild.xid, [user.xid]) == set()

    async def test_unknown_leaves_the_record_alone(
        self,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """An error is not evidence of leaving, so nothing is written either way."""
        guild = factories.guild.create(xid=907)
        user = factories.user.create(xid=9007)
        factories.guild_member.create(guild_xid=guild.xid, user_xid=user.xid)
        mocker.patch(
            "spellbot.web.api.analytics.check_guild_member",
            AsyncMock(return_value=Membership.UNKNOWN),
        )

        result = await analytics.check_membership_and_update(guild.xid, self.players(user.xid))

        assert result[0]["left_server"] is False
        assert await analytics.recently_checked_members(guild.xid, [user.xid]) == set()
