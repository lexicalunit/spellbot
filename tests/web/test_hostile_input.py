# Copyright (c) 2026 spellbot@lexicalunit.com

"""Malformed ids, query values, and cookies get a 4xx or a normal page, never a 500."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.models import GameStatus

if TYPE_CHECKING:
    from aiohttp.client import ClientSession

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db

# Too big for a bigint, too big for an int, and not ASCII digits at all.
BAD_IDS = ["9" * 30, "99999999999", "²", "-1", "+5"]
GET_ROUTES = [
    "/g/{x}",
    "/g/{x}/c/1",
    "/g/1/c/{x}",
    "/u/{x}",
    "/game/{x}",
    "/g/{x}/awards",
    "/g/{x}/c/1/export.csv",
    "/g/1/c/{x}/export.csv",
    "/u/{x}/export.csv",
    "/g/{x}/analytics",
    "/g/{x}/analytics/summary",
    "/g/{x}/audit",
    "/g/1/c/{x}/audit",
    "/queues/g/{x}",
]
POST_ROUTES = [
    "/g/{x}/settings",
    "/g/{x}/c/1/settings",
    "/g/1/c/{x}/settings",
    "/g/{x}/c/1/forget",
    "/g/1/awards/{x}/update",
    "/g/1/awards/{x}/delete",
    "/g/{x}/promote",
    "/u/{x}/blocks/add",
    "/u/1/blocks/{x}/remove",
    "/queues/g/{x}/notify",
]
BAD_QUERIES = [
    "/u/1?page=" + "9" * 30,
    "/u/1?page=" + "9" * 5000,
    "/g/1/c/1?page=99999999999999999",
    "/g/1/audit?page=" + "9" * 30,
    "/u/1?from=9999-12-31&to=9999-12-31",
    "/u/1?from=0001-01-01&to=0001-01-01",
    "/g/1/analytics?expires=99999999999&sig=%C3%A9",
]
BAD_COOKIES = [
    {"timezone_offset": "9" * 30},
    {"timezone_offset": "99999999999", "timezone_name": "UTC"},
    {"timezone_offset": "60", "timezone_name": "../../etc/passwd"},
    {"timezone_offset": "60", "timezone_name": "America/"},
]


@pytest.fixture
def records(factories: Factories) -> None:
    """Create a guild 1 / channel 1 game played by user 1, so pages have rows to format."""
    user = factories.user.create(xid=1, name="user")
    guild = factories.guild.create(xid=1, name="guild")
    channel = factories.channel.create(xid=1, name="channel", guild=guild)
    game = factories.game.create(
        id=1,
        seats=2,
        status=GameStatus.STARTED.value,
        guild=guild,
        channel=channel,
        started_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
    factories.play.create(game_id=game.id, user_xid=user.xid)


@pytest.mark.asyncio
@pytest.mark.usefixtures("records")
class TestHostileInput:
    @pytest.mark.parametrize("route", GET_ROUTES)
    async def test_get_with_bad_ids(self, mod_client: ClientSession, route: str) -> None:
        for bad_id in BAD_IDS:
            resp = await mod_client.get(route.format(x=bad_id), allow_redirects=False)
            assert resp.status < 500, route.format(x=bad_id)

    @pytest.mark.parametrize("route", POST_ROUTES)
    async def test_post_with_bad_ids(self, mod_client: ClientSession, route: str) -> None:
        for bad_id in [*BAD_IDS, "5"]:  # 5 is a valid id with no guild behind it
            resp = await mod_client.post(
                route.format(x=bad_id),
                data={"target": "9" * 30, "name": "award"},
                allow_redirects=False,
            )
            assert resp.status < 500, route.format(x=bad_id)

    @pytest.mark.parametrize("path", BAD_QUERIES)
    async def test_bad_query_values(self, mod_client: ClientSession, path: str) -> None:
        resp = await mod_client.get(path, allow_redirects=False)
        assert resp.status < 500

    @pytest.mark.parametrize("cookies", BAD_COOKIES)
    @pytest.mark.parametrize("path", ["/u/1", "/u/1?from=2020-01-01", "/g/1", "/game/1"])
    async def test_bad_timezone_cookies(
        self,
        mod_client: ClientSession,
        cookies: dict[str, str],
        path: str,
    ) -> None:
        resp = await mod_client.get(path, cookies=cookies)
        assert resp.status == 200
