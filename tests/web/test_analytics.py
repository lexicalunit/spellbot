from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.utils import generate_signed_url

if TYPE_CHECKING:
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
class TestWebAnalyticsData:
    """Tests for the data endpoint (returns JSON with analytics)."""

    async def test_analytics_data_happy_path(
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
            f"/g/{guild.xid}/analytics/data?expires={query['expires'][0]}&sig={query['sig'][0]}"
        )

        resp = await client.get(data_path)
        assert resp.status == 200
        data = await resp.json()
        assert data["guild_name"] == "test-guild"
        assert data["total_games"] == 1
        assert data["unique_players"] == 1

    async def test_analytics_data_invalid_guild(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(99999, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        data_path = f"/g/99999/analytics/data?expires={query['expires'][0]}&sig={query['sig'][0]}"

        resp = await client.get(data_path)
        assert resp.status == 404

    async def test_analytics_data_missing_signature(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/201/analytics/data")
        assert resp.status == 403

    async def test_analytics_data_expired_signature(
        self,
        client: ClientSession,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch("spellbot.utils.time.time", return_value=1000.0)
        url = generate_signed_url(201, expires_in_minutes=10)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        data_path = f"/g/201/analytics/data?expires={query['expires'][0]}&sig={query['sig'][0]}"

        mocker.patch("spellbot.utils.time.time", return_value=2000.0)
        resp = await client.get(data_path)
        assert resp.status == 403

    async def test_analytics_data_invalid_signature(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/201/analytics/data?expires=9999999999&sig=bad")
        assert resp.status == 403

    async def test_analytics_data_bad_guild_in_url(
        self,
        client: ClientSession,
    ) -> None:
        resp = await client.get("/g/notanumber/analytics/data?expires=9999999999&sig=bad")
        assert resp.status == 404
