from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from freezegun.api import FrozenDateTimeFactory
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestWebRecord:
    async def test_user_record(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=101, name="user-1")
        user2 = factories.user.create(xid=102, name="user-2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=901)
        factories.play.create(game_id=game.id, user_xid=user1.xid, og_guild_xid=guild.xid, pin="A")
        factories.play.create(game_id=game.id, user_xid=user2.xid, og_guild_xid=guild.xid, pin="B")
        token = factories.token.create(key="XYZ")

        # all data correct
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": True}}

        # user_xid wrong
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid + 200, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # guild_xid wrong
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid + 200, "pin": "A"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # pin wrong
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "C"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # game_id wrong
        resp = await client.post(
            f"/api/game/{game.id + 100}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # missing authentication
        resp = await client.post("/api/game/1/verify", json={})
        assert resp.status == 401
        assert await resp.json() == {"error": "Missing or invalid Authorization header"}

        # bad authentication
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer BOGUS"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 403
        assert await resp.json() == {"error": "Unauthorized"}

        # missing the user_xid
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "missing key: 'user_xid'"}

        # missing the guild_xid
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "pin": "A"},
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "missing key: 'guild_xid'"}

        # missing the pin
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid},
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "missing key: 'pin'"}

        # invalid game_id
        resp = await client.post(
            "/api/game/FOO/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={},
        )
        assert resp.status == 400
        assert await resp.json() == {
            "error": "invalid literal for int() with base 10: 'FOO'",
        }

        # unexpected error
        mocker.patch(
            "spellbot.services.plays.PlaysService.verify_game_pin",
            side_effect=Exception("BOOM"),
        )
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 500
        assert await resp.json() == {"error": "BOOM"}
