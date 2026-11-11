# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp
import pytest
import pytest_asyncio
from aiohttp.client import _BaseRequestContextManager
from sqlalchemy import select

from spellbot.data import PostData
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat
from spellbot.models import Game, GameStatus, Play, User
from spellbot.services import plays
from spellbot.web import builder
from spellbot.web.api import rest
from spellbot.web.api.rest import (
    close_http_session,
    game_record_embed,
    post_with_retry,
    reply,
    retry_if_not_unrecoverable,
    send_dm,
    send_message,
)
from spellbot.web.tools import RATE_LIMIT
from tests.mocks import create_mock_game, create_mock_user
from tests.mocks.decoys import ANY, async_raising, async_returning
from tests.mocks.redis import FakeRedis, serve_redis

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from aiohttp.client import ClientResponse, ClientSession
    from decoy import Decoy
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories, Stub
    from tests.mocks.http import JSON

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def reset_http_session() -> AsyncGenerator[None]:
    yield
    await close_http_session()


@pytest.mark.asyncio
class TestWebRecord:
    async def test_user_record(  # noqa: PLR0915
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
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
        factories.play.create(
            game_id=game.id,
            user_xid=user1.xid,
            og_guild_xid=guild.xid,
            pin="111111",
        )
        factories.play.create(
            game_id=game.id,
            user_xid=user2.xid,
            og_guild_xid=guild.xid,
            pin="222222",
        )
        factories.token.create(key="XYZ")

        # all data correct
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": True}}

        # user_xid wrong
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid + 200, "guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # ids too big for the database are rejected rather than queried
        for body in (
            {"user_xid": 2**63, "guild_xid": guild.xid, "pin": "111111"},
            {"user_xid": user1.xid, "guild_xid": str(2**63), "pin": "111111"},
        ):
            resp = await client.post(
                f"/api/game/{game.id}/verify",
                headers={"Authorization": "Bearer XYZ"},
                json=body,
            )
            assert resp.status == 400

        # guild_xid wrong
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid + 200, "pin": "111111"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # pin wrong
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "333333"},
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"verified": False}}

        # game_id wrong
        resp = await client.post(
            f"/api/game/{game.id + 100}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "111111"},
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
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 403
        assert await resp.json() == {"error": "Unauthorized"}

        # bad authentication with rate limiting
        rate_limited_fake = stub(builder, "rate_limited")
        decoy.when(await rate_limited_fake(ANY), ignore_extra_args=True).then_return(True)
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer BOGUS"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Too many requests"}

        # missing the user_xid
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "missing key: 'user_xid'"}

        # missing the guild_xid
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "pin": "111111"},
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "missing key: 'guild_xid'"}

        # missing the pin
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid},
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "missing key: 'pin'"}

        # invalid game_id
        resp = await client.post(
            "/api/game/FOO/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={},
        )
        assert resp.status == 400
        assert await resp.json() == {
            "error": "not an id: 'FOO'",
        }

        # unexpected error
        monkeypatch.setattr(plays, "verify_game_pin", async_raising(Exception("BOOM")))
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 500
        # The exception's text isn't sent back; it can include SQL.
        assert await resp.json() == {"error": "Internal error"}

        # Test rate limiting on ValueError
        monkeypatch.setattr(rest, "rate_limited", async_returning(True))
        resp = await client.post(
            "/api/game/FOO/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}

        # Test rate limiting on KeyError
        monkeypatch.setattr(rest, "rate_limited", async_returning(True))
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"guild_xid": guild.xid, "pin": "111111"},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}


@pytest.mark.asyncio
class TestVerifyPinLimit:
    """Wrong PINs count against the game, and past the limit no PIN is checked at all."""

    @pytest_asyncio.fixture
    async def play(self, factories: Factories) -> Play:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(id=1, seats=2, guild=guild, channel=channel)
        user = factories.user.create(xid=101, name="user")
        factories.token.create(key="XYZ")
        return factories.play.create(
            game_id=game.id,
            user_xid=user.xid,
            og_guild_xid=guild.xid,
            pin="123456",
        )

    @staticmethod
    async def verify(client: ClientSession, play: Play, pin: object) -> ClientResponse:
        return await client.post(
            f"/api/game/{play.game_id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json={"user_xid": play.user_xid, "guild_xid": play.og_guild_xid, "pin": pin},
        )

    async def test_a_right_pin_is_refused_once_the_game_is_over_the_limit(
        self,
        client: ClientSession,
        play: Play,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        redis = FakeRedis(data={"game_verify:1": str(RATE_LIMIT)})
        serve_redis(monkeypatch, redis)
        resp = await self.verify(client, play, "123456")
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}
        assert redis.evals == []  # refused without counting or checking

    async def test_only_wrong_pins_count(
        self,
        client: ClientSession,
        play: Play,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        redis = FakeRedis(data={"game_verify:1": str(RATE_LIMIT - 1)})
        serve_redis(monkeypatch, redis)

        resp = await self.verify(client, play, "123456")
        assert await resp.json() == {"result": {"verified": True}}
        assert redis.evals == []

        resp = await self.verify(client, play, "654321")
        assert await resp.json() == {"result": {"verified": False}}
        [(_script, _numkeys, key, _window)] = redis.evals
        assert key == "game_verify:1"

    @pytest.mark.parametrize("pin", ["12345", "1234567", "12345a", "١٢٣٤٥٦", 123456, None])
    async def test_pin_must_be_a_six_digit_string(
        self,
        client: ClientSession,
        play: Play,
        pin: object,
    ) -> None:
        resp = await self.verify(client, play, pin)
        assert resp.status == 400
        assert await resp.json() == {"error": "pin must be a string of 6 digits"}

    @pytest.mark.parametrize("body", [[1, 2, 3], "text", 5])
    async def test_body_must_be_an_object(
        self,
        client: ClientSession,
        play: Play,
        body: object,
    ) -> None:
        resp = await client.post(
            f"/api/game/{play.game_id}/verify",
            headers={"Authorization": "Bearer XYZ"},
            json=body,
        )
        assert resp.status == 400
        assert await resp.json() == {"error": "Verify request must be a JSON object"}


class TestCommanderText:
    def test_plain_name_is_unchanged(self) -> None:
        assert rest.commander_text("  Kenrith, the Returned King ") == "Kenrith, the Returned King"

    def test_markdown_and_mentions_are_escaped(self) -> None:
        text = rest.commander_text("**[free](https://evil.example)** <@123> @everyone")
        assert text == (
            r"\*\*\[free\]\(https://evil.example\)\*\* \<@" + "\u200b" + "123> @\u200beveryone"
        )

    def test_text_is_one_line(self) -> None:
        text = rest.commander_text("Atraxa\n# Free Nitro\n> click")
        assert text == "Atraxa # Free Nitro > click"

    def test_long_text_is_cut(self) -> None:
        assert len(rest.commander_text("x" * 500)) == rest.MAX_COMMANDER_LENGTH


class TestReply:
    def test_reply_success(self) -> None:
        response = reply({"key": "value"})
        assert response.status == 200

    def test_reply_with_error(self) -> None:
        response = reply(error="Something went wrong")
        assert response.status == 500

    def test_reply_with_custom_status(self) -> None:
        response = reply({"key": "value"}, status=201)
        assert response.status == 201


class TestRetryIfNotUnrecoverable:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            pytest.param(400, False, id="bad_request"),
            pytest.param(401, False, id="unauthorized"),
            pytest.param(403, False, id="forbidden"),
            pytest.param(404, False, id="not_found"),
            pytest.param(500, True, id="internal_error"),
            pytest.param(502, True, id="bad_gateway"),
            pytest.param(503, True, id="service_unavailable"),
            pytest.param(504, True, id="gateway_timeout"),
        ],
    )
    def test_client_response_error(self, decoy: Decoy, status: int, expected: bool) -> None:
        exc = aiohttp.ClientResponseError(decoy.mock(cls=aiohttp.RequestInfo), (), status=status)
        assert retry_if_not_unrecoverable(exc) is expected

    def test_non_client_response_error(self) -> None:
        exc = ValueError("Some error")
        assert retry_if_not_unrecoverable(exc) is True


@pytest.mark.asyncio
class TestPostWithRetry:
    @staticmethod
    async def discord_session(
        decoy: Decoy,
        method: str,
        body: Mapping[str, JSON],
    ) -> aiohttp.ClientSession:
        """Build a session whose `method` request to `/test/path` answers with `body`."""
        response = decoy.mock(cls=aiohttp.ClientResponse)
        decoy.when(await response.json()).then_return(body)
        request = decoy.mock(cls=_BaseRequestContextManager)
        decoy.when(await request.__aenter__()).then_return(response)
        session = decoy.mock(cls=aiohttp.ClientSession)
        url = "https://discord.com/api/test/path"
        decoy.when(getattr(session, method)(url, headers=ANY, json=ANY)).then_return(request)
        return session

    async def test_post_with_retry_success(self, decoy: Decoy) -> None:
        session = await self.discord_session(decoy, "post", {"id": "12345"})
        result = await post_with_retry(session, "/test/path", {"key": "value"})
        assert result == {"id": "12345"}

    async def test_post_with_retry_get_method(self, decoy: Decoy) -> None:
        session = await self.discord_session(decoy, "get", {"data": "test"})
        result = await post_with_retry(session, "/test/path", method="get")
        assert result == {"data": "test"}


class TestGameRecordEmbed:
    def test_with_winner(self) -> None:
        game_data = create_mock_game(game_id=1)
        game_data.guild_xid = 123
        game_data.channel_xid = 456
        game_data.started_at = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        now = datetime.now(tz=UTC)
        game_data.posts = [
            PostData(
                created_at=now,
                updated_at=now,
                game_id=1,
                guild_xid=123,
                channel_xid=456,
                message_xid=789,
            ),
        ]
        players = [
            create_mock_user(xid=101, name="Player1"),
            create_mock_user(xid=102, name="Player2"),
        ]
        commanders: dict[int | None, str] = {101: "Atraxa", 102: "Kenrith"}
        result = game_record_embed(
            game_data=game_data,
            players=players,
            commanders=commanders,
            winner_xid=101,
            tracker_xid=102,
            tracker_name="Player2",
        )
        assert "embeds" in result
        assert "🎉 Winner 🎉" in str(result)
        assert "Atraxa" in str(result)
        assert "tracked by <@102> (Player2)." in result["embeds"][0]["description"]

    def test_without_winner(self) -> None:

        game_data = create_mock_game(game_id=1)
        game_data.guild_xid = 123
        game_data.channel_xid = 456
        game_data.started_at = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        now = datetime.now(tz=UTC)
        game_data.posts = [
            PostData(
                created_at=now,
                updated_at=now,
                game_id=1,
                guild_xid=123,
                channel_xid=456,
                message_xid=789,
            ),
        ]
        players = [
            create_mock_user(xid=101, name="Player1"),
            create_mock_user(xid=102, name="Player2"),
        ]
        commanders: dict[int | None, str] = {101: "Atraxa", 102: "Kenrith"}
        result = game_record_embed(
            game_data=game_data,
            players=players,
            commanders=commanders,
            winner_xid=None,
            tracker_xid=102,
            tracker_name="Player2",
        )
        assert "embeds" in result
        assert "No Winner" in str(result)
        assert "Draw game" in str(result)

    def test_unknown_tracker_name(self) -> None:
        game_data = create_mock_game(game_id=1)
        game_data.guild_xid = 123
        game_data.channel_xid = 456
        game_data.started_at = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        players = [
            create_mock_user(xid=101, name="Player1"),
            create_mock_user(xid=102, name="Player2"),
        ]
        commanders: dict[int | None, str] = {101: "Atraxa", 102: "Kenrith"}
        result = game_record_embed(
            game_data=game_data,
            players=players,
            commanders=commanders,
            winner_xid=101,
            tracker_xid=999,
            tracker_name=None,
        )
        assert "tracked by <@999>." in result["embeds"][0]["description"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_http_session")
class TestSendMessage:
    async def test_send_message_success(self, decoy: Decoy, stub: Stub) -> None:
        mock_post = stub(rest, "post_with_retry")
        decoy.when(
            await mock_post(ANY, "/channels/123/messages", {"content": "Hello"}),
        ).then_return({"id": "12345"})
        result = await send_message(123, {"content": "Hello"})
        assert result == {"id": "12345"}

    async def test_send_message_failure(self, decoy: Decoy, stub: Stub) -> None:
        post_with_retry_fake = stub(rest, "post_with_retry")
        decoy.when(await post_with_retry_fake(ANY, ANY), ignore_extra_args=True).then_raise(
            Exception("Connection error")
        )
        result = await send_message(123, {"content": "Hello"})
        assert result is None

    async def test_session_is_reused(self, decoy: Decoy, stub: Stub) -> None:
        """Repeated calls share a single aiohttp ClientSession."""
        post_with_retry_fake = stub(rest, "post_with_retry")
        decoy.when(await post_with_retry_fake(ANY, ANY), ignore_extra_args=True).then_return(
            {"id": "12345"}
        )
        await send_message(123, {"content": "Hello"})
        first = rest.shared.session
        await send_message(123, {"content": "Hello"})
        assert rest.shared.session is first


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_http_session")
class TestSendDm:
    async def test_send_dm_success(self, decoy: Decoy, stub: Stub) -> None:
        mock_post = stub(rest, "post_with_retry")
        decoy.when(await mock_post(ANY, ANY), ignore_extra_args=True).then_return(
            {"id": "channel123"},
            {"id": "message456"},
        )
        await send_dm(101, {"content": "Hello"})
        # The second call posts the message to the DM channel the first call opened.
        decoy.verify(await mock_post(ANY, "/channels/channel123/messages", {"content": "Hello"}))

    async def test_send_dm_unrecoverable_error(
        self,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        exc = aiohttp.ClientResponseError(decoy.mock(cls=aiohttp.RequestInfo), (), status=403)
        post_with_retry_fake = stub(rest, "post_with_retry")
        decoy.when(await post_with_retry_fake(ANY, ANY), ignore_extra_args=True).then_raise(exc)
        # Should not raise, just log
        await send_dm(101, {"content": "Hello"})

    async def test_send_dm_recoverable_client_error(
        self,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # 500 is not in UNRECOVERABLE, so it should be re-raised and caught by outer except
        exc = aiohttp.ClientResponseError(decoy.mock(cls=aiohttp.RequestInfo), (), status=500)
        post_with_retry_fake = stub(rest, "post_with_retry")
        decoy.when(await post_with_retry_fake(ANY, ANY), ignore_extra_args=True).then_raise(exc)
        # Should not raise, just log
        await send_dm(101, {"content": "Hello"})

    async def test_send_dm_other_exception(self, decoy: Decoy, stub: Stub) -> None:
        post_with_retry_fake = stub(rest, "post_with_retry")
        decoy.when(await post_with_retry_fake(ANY, ANY), ignore_extra_args=True).then_raise(
            Exception("Network error")
        )
        # Should not raise, just log
        await send_dm(101, {"content": "Hello"})


@pytest.mark.asyncio
class TestGameRecordEndpoint:
    async def test_game_record_success(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=1001, name="user-1")
        user2 = factories.user.create(xid=1002, name="user-2")
        guild = factories.guild.create(xid=2001, name="guild")
        channel = factories.channel.create(xid=3001, name="channel", guild=guild)
        game = factories.game.create(
            id=1001,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            started_at=datetime.now(tz=UTC),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9001)
        factories.play.create(
            game_id=game.id,
            user_xid=user1.xid,
            og_guild_xid=guild.xid,
            pin="A",
        )
        factories.play.create(
            game_id=game.id,
            user_xid=user2.xid,
            og_guild_xid=guild.xid,
            pin="B",
        )
        factories.token.create(key="RECORD1")

        send_dm_fake = stub(rest, "send_dm")
        decoy.when(await send_dm_fake(ANY, ANY), ignore_extra_args=True).then_return(None)

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD1"},
            json={
                "winner": user1.xid,
                "tracker": user2.xid,
                "players": [
                    {"xid": user1.xid, "commander": "Atraxa"},
                    {"xid": user2.xid, "commander": "Kenrith"},
                ],
            },
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["result"]["success"] is True

    async def test_game_record_not_found(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        factories.token.create(key="RECORD2")

        resp = await client.post(
            "/api/game/99999/record",
            headers={"Authorization": "Bearer RECORD2"},
            json={
                "winner": 101,
                "tracker": 102,
                "players": [{"xid": 101, "commander": "Atraxa"}],
            },
        )
        assert resp.status == 404
        data = await resp.json()
        assert data["error"] == "Game not found"

    async def test_game_record_invalid_game_id(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        factories.token.create(key="RECORD_INVALID")

        resp = await client.post(
            "/api/game/not-a-number/record",
            headers={"Authorization": "Bearer RECORD_INVALID"},
            json={
                "winner": 101,
                "tracker": 102,
                "players": [{"xid": 101, "commander": "Atraxa"}],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Invalid game ID"

    async def test_game_record_missing_tracker(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        guild = factories.guild.create(xid=2099, name="guild")
        channel = factories.channel.create(xid=3099, name="channel", guild=guild)
        game = factories.game.create(
            id=1099,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.token.create(key="RECORD_NOTRACKER")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD_NOTRACKER"},
            json={
                "winner": 101,
                "players": [{"xid": 101, "commander": "Atraxa"}],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Tracker ID is required"

    async def test_game_record_no_players(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        guild = factories.guild.create(xid=2002, name="guild")
        channel = factories.channel.create(xid=3002, name="channel", guild=guild)
        game = factories.game.create(
            id=1002,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.token.create(key="RECORD3")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD3"},
            json={
                "winner": 101,
                "tracker": 102,
                "players": [],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "No players provided"

    @pytest.mark.parametrize(
        ("body", "error"),
        [
            pytest.param({"data": "not json"}, "Invalid JSON body", id="malformed"),
            pytest.param({"json": [1, 2]}, "Record must be a JSON object", id="not-object"),
            pytest.param(
                {"json": {"tracker": 102, "players": {"xid": 1}}},
                "Invalid player data",
                id="players-not-list",
            ),
            pytest.param(
                {"json": {"tracker": 102, "players": ["1001"]}},
                "Invalid player data",
                id="player-not-object",
            ),
            pytest.param(
                {"json": {"tracker": 102, "players": [{"xid": 1001, "commander": {"a": 1}}]}},
                "Invalid player data",
                id="commander-not-string",
            ),
        ],
    )
    async def test_game_record_bad_body(
        self,
        client: ClientSession,
        factories: Factories,
        body: dict[str, Any],
        error: str,
    ) -> None:
        guild = factories.guild.create(xid=2010, name="guild")
        channel = factories.channel.create(xid=3010, name="channel", guild=guild)
        game = factories.game.create(id=1010, seats=2, guild=guild, channel=channel)
        factories.token.create(key="RECORD10")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD10"},
            **body,
        )
        assert resp.status == 400
        assert (await resp.json())["error"] == error

    async def test_game_record_mismatched_players(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test game record with mismatched player count."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        user1 = factories.user.create(xid=1003, name="user-3")
        guild = factories.guild.create(xid=2003, name="guild")
        channel = factories.channel.create(xid=3003, name="channel", guild=guild)
        game = factories.game.create(
            id=1003,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        factories.play.create(
            game_id=game.id,
            user_xid=user1.xid,
            og_guild_xid=guild.xid,
            pin="A",
        )
        factories.token.create(key="RECORD4")

        # Provide 2 players but only 1 play exists
        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD4"},
            json={
                "winner": user1.xid,
                "tracker": user1.xid,
                "players": [
                    {"xid": user1.xid, "commander": "Atraxa"},
                    {"xid": 9999, "commander": "Unknown"},  # Non-existent player
                ],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Players don't match the game's players"

    @pytest.mark.parametrize(
        "listed",
        [
            pytest.param([1011, 4242], id="stranger-swapped-in"),
            pytest.param([1011, 1011], id="player-listed-twice"),
            pytest.param([1011, 1012, 4242], id="stranger-added"),
        ],
    )
    async def test_game_record_only_dms_the_games_players(
        self,
        client: ClientSession,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
        listed: list[int],
    ) -> None:
        send_dm_fake = stub(rest, "send_dm")
        guild = factories.guild.create(xid=2011, name="guild")
        channel = factories.channel.create(xid=3011, name="channel", guild=guild)
        game = factories.game.create(
            id=1011,
            seats=2,
            status=GameStatus.STARTED.value,
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
        )
        for xid in (1011, 1012):
            factories.user.create(xid=xid, name=f"user-{xid}")
            factories.play.create(game_id=game.id, user_xid=xid)
        factories.user.create(xid=4242, name="stranger")
        factories.token.create(key="RECORD11")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD11"},
            json={
                "tracker": 1011,
                "players": [{"xid": xid, "commander": "Atraxa"} for xid in listed],
            },
        )

        assert resp.status == 400
        assert (await resp.json())["error"] == "Players don't match the game's players"
        decoy.verify(await send_dm_fake(ANY, ANY), times=0)

    async def test_game_record_sanitizes_commanders(
        self,
        client: ClientSession,
        factories: Factories,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sent: list[dict[str, Any]] = []

        async def send_dm(user_xid: int, message: dict[str, Any]) -> None:
            sent.append(message)

        monkeypatch.setattr(rest, "send_dm", send_dm)
        guild = factories.guild.create(xid=2012, name="guild")
        channel = factories.channel.create(xid=3012, name="channel", guild=guild)
        game = factories.game.create(
            id=1012,
            seats=1,
            status=GameStatus.STARTED.value,
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
        )
        factories.user.create(xid=1013, name="player")
        factories.play.create(game_id=game.id, user_xid=1013)
        factories.token.create(key="RECORD12")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD12"},
            json={
                "tracker": 1013,
                "players": [{"xid": 1013, "commander": "[Claim prize](https://evil.example)"}],
            },
        )

        assert resp.status == 200
        [message] = sent
        players_field = message["embeds"][0]["fields"][-1]["value"]
        assert "[Claim prize](https://evil.example)" not in players_field
        assert r"\[Claim prize\]\(https://evil.example\)" in players_field

    async def test_game_record_with_username_tracker(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test that usernames can be used instead of xids for tracker."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        send_dm_fake = stub(rest, "send_dm")
        decoy.when(await send_dm_fake(ANY, ANY), ignore_extra_args=True).then_return(None)

        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        user1 = factories.user.create(xid=101, name="PlayerOne")
        user2 = factories.user.create(xid=102, name="PlayerTwo")
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
        )
        factories.play.create(user_xid=user1.xid, game_id=game.id)
        factories.play.create(user_xid=user2.xid, game_id=game.id)
        factories.token.create(key="RECORD5")

        # Use username instead of xid for tracker
        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD5"},
            json={
                "winner": user1.xid,
                "tracker": "PlayerTwo",  # Username instead of xid
                "players": [
                    {"xid": user1.xid, "commander": "Atraxa"},
                    {"xid": user2.xid, "commander": "Kenrith"},
                ],
            },
        )
        assert resp.status == 200

    @pytest.mark.parametrize("tracker_in_db", [True, False])
    async def test_game_record_tracker_not_a_player(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        decoy: Decoy,
        stub: Stub,
        tracker_in_db: bool,
    ) -> None:
        """Test that the tracker doesn't have to be one of the players in the game."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))
        send_dm_fake = stub(rest, "send_dm")
        decoy.when(await send_dm_fake(ANY, ANY), ignore_extra_args=True).then_return(None)

        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        user1 = factories.user.create(xid=101, name="PlayerOne")
        user2 = factories.user.create(xid=102, name="PlayerTwo")
        if tracker_in_db:
            factories.user.create(xid=103, name="Tracker")
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
        )
        factories.play.create(user_xid=user1.xid, game_id=game.id)
        factories.play.create(user_xid=user2.xid, game_id=game.id)
        factories.token.create(key="RECORD_NON_PLAYER_TRACKER")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD_NON_PLAYER_TRACKER"},
            json={
                "winner": user1.xid,
                "tracker": 103,
                "players": [
                    {"xid": user1.xid, "commander": "Atraxa"},
                    {"xid": user2.xid, "commander": "Kenrith"},
                ],
            },
        )
        assert resp.status == 200

    async def test_game_record_tracker_not_found(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test that invalid tracker username returns error."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))

        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
        )
        factories.token.create(key="RECORD6")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD6"},
            json={
                "tracker": "NonExistentUser",
                "players": [{"xid": 101, "commander": "Atraxa"}],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Tracker not found"

    async def test_game_record_invalid_player_data(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test that missing xid or commander in player data returns error."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))

        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        user1 = factories.user.create(xid=101, name="PlayerOne")
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
        )
        factories.token.create(key="RECORD7")

        # Missing "commander" field
        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD7"},
            json={
                "tracker": user1.xid,
                "players": [{"xid": user1.xid}],  # Missing commander
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Invalid player data"

    async def test_game_record_player_not_found(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test that invalid player username returns error."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))

        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        user1 = factories.user.create(xid=101, name="PlayerOne")
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
        )
        factories.token.create(key="RECORD8")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD8"},
            json={
                "tracker": user1.xid,
                "players": [{"xid": "NonExistentPlayer", "commander": "Atraxa"}],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Player not found: NonExistentPlayer"

    async def test_game_record_invalid_tracker_type(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        """Test that non-string, non-int tracker returns error."""
        freezer.move_to(datetime(2020, 1, 1, tzinfo=UTC))

        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
        )
        factories.token.create(key="RECORD9")

        # Use a list as tracker (not string or int)
        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD9"},
            json={
                "tracker": ["invalid", "type"],
                "players": [{"xid": 101, "commander": "Atraxa"}],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "Tracker not found"

    @pytest.mark.parametrize("tracker", [2**63, str(2**63)])
    async def test_game_record_tracker_id_too_big(
        self,
        client: ClientSession,
        factories: Factories,
        tracker: int | str,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game = factories.game.create(id=1, seats=2, guild=guild, channel=channel)
        factories.token.create(key="RECORD10")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": "Bearer RECORD10"},
            json={"tracker": tracker, "players": [{"xid": 101, "commander": "Atraxa"}]},
        )
        assert resp.status == 400
        assert (await resp.json())["error"] == "Tracker not found"


class TestPayloadId:
    @pytest.mark.parametrize(("value", "expected"), [(5, 5), ("5", 5), (2**63 - 1, 2**63 - 1)])
    def test_numbers_and_digit_strings(self, value: int | str, expected: int) -> None:
        assert rest.payload_id(value, User.xid) == expected

    @pytest.mark.parametrize("value", [2**63, -5, 5.0, True, None, [5], " 5", "5x"])
    def test_rejects_everything_else(self, value: object) -> None:
        with pytest.raises(ValueError, match="id"):
            rest.payload_id(value, User.xid)


@pytest.mark.asyncio
class TestGameMetadataEndpoint:
    async def test_game_metadata_success(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2101, name="guild")
        channel = factories.channel.create(xid=3101, name="channel", guild=guild)
        game = factories.game.create(
            id=1101,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
        )
        factories.token.create(key="META1")

        report = {
            "source": "convoke",
            "duration_minutes": 42,
            "winner": {"name": "PlayerOne", "commander": "Atraxa"},
            "players": [
                {"name": "PlayerOne", "commander": "Atraxa", "turn_order": 1, "is_winner": True},
                {"name": "PlayerTwo", "commander": "Kenrith", "turn_order": 2},
            ],
            "links": {"mythic_track": "https://mythictrack.com/g/abc"},
        }
        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META1"},
            json=report,
        )
        assert resp.status == 200
        assert await resp.json() == {"result": {"success": True}}

        # The stored report is surfaced on the game detail view.
        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"] == report

    async def test_game_metadata_starts_unstarted_game(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2120, name="guild")
        channel = factories.channel.create(xid=3120, name="channel", guild=guild)
        game = factories.game.create(id=1120, guild=guild, channel=channel, war_id="war-a")
        user = factories.user.create(xid=4120)
        factories.token.create(key="META20")

        report = {
            "source": "convoke",
            "started_at": "2026-09-19T19:22:22Z",
            "players": [{"xid": str(user.xid), "name": "p1"}, {"xid": None, "name": "p2"}],
        }
        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META20"},
            json=report,
        )

        assert resp.status == 200
        DatabaseSession.expire_all()
        started = await DatabaseSession.get(Game, game.id)
        assert started is not None
        assert started.status == GameStatus.STARTED.value
        reported_start = datetime(2026, 9, 19, 19, 22, 22, tzinfo=UTC)
        assert started.started_at == reported_start.replace(tzinfo=None)
        plays = await DatabaseSession.scalars(select(Play.user_xid).where(Play.game_id == game.id))
        assert list(plays) == [user.xid]

    async def test_game_metadata_forwards_to_castlog(
        self,
        client: ClientSession,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild = factories.guild.create(xid=2110, name="guild")
        channel = factories.channel.create(xid=3110, name="channel", guild=guild)
        game = factories.game.create(id=1110, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META10")
        mock_report_match = stub(rest.castlog, "report_match")
        decoy.when(await mock_report_match(payload=ANY), ignore_extra_args=True).then_return(
            {"match_id": "abc-123"}
        )

        report = {"source": "convoke", "players": [{"xid": 501, "commander": "Atraxa"}]}
        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META10"},
            json=report,
        )

        assert resp.status == 200
        # The game id only arrives in the URL, so it is added to the forwarded body to give
        # Castlog a stable key for de-duplicating repeat reports of the same match.
        decoy.verify(await mock_report_match(report | {"spellbot_game_id": game.id}), times=1)

    async def test_game_metadata_does_not_forward_stale_report_to_castlog(
        self,
        client: ClientSession,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild = factories.guild.create(xid=2114, name="guild")
        channel = factories.channel.create(xid=3114, name="channel", guild=guild)
        game = factories.game.create(id=1114, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META14")
        mock_report_match = stub(rest.castlog, "report_match")
        decoy.when(await mock_report_match(payload=ANY), ignore_extra_args=True).then_return(None)
        headers = {"Authorization": "Bearer META14"}

        newer = {"source": "convoke", "reported_at": "2026-07-11T18:30:00+00:00", "turns": 20}
        older = {"source": "convoke", "reported_at": "2026-07-11T18:00:00+00:00", "turns": 5}

        url = f"/api/game/{game.id}/metadata"
        assert (await client.post(url, headers=headers, json=newer)).status == 200
        assert (await client.post(url, headers=headers, json=older)).status == 200

        # The older report is accepted-and-ignored locally, so Castlog must not be told
        # about it either -- doing so would regress Castlog to data we rejected ourselves.
        decoy.verify(await mock_report_match(newer | {"spellbot_game_id": game.id}), times=1)

    async def test_game_metadata_accumulates_links_across_reports(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2115, name="guild")
        channel = factories.channel.create(xid=3115, name="channel", guild=guild)
        game = factories.game.create(id=1115, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META15")
        headers = {"Authorization": "Bearer META15"}

        first = await client.post(
            f"/api/game/{game.id}/metadata",
            headers=headers,
            json={
                "source": "convoke",
                "reported_at": "2026-07-11T18:00:00+00:00",
                "links": {"mythic_track": "https://mythictrack.com/g/abc"},
            },
        )
        assert first.status == 200
        # A later report that only knows about its own tracker must not drop the other link.
        second = await client.post(
            f"/api/game/{game.id}/metadata",
            headers=headers,
            json={
                "source": "convoke",
                "reported_at": "2026-07-11T18:30:00+00:00",
                "links": {"castlog": "https://app.castlog.gg/match/abc-123"},
            },
        )
        assert second.status == 200

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"]["links"] == {
            "mythic_track": "https://mythictrack.com/g/abc",
            "castlog": "https://app.castlog.gg/match/abc-123",
        }

    async def test_game_metadata_survives_castlog_failure(
        self,
        client: ClientSession,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild = factories.guild.create(xid=2111, name="guild")
        channel = factories.channel.create(xid=3111, name="channel", guild=guild)
        game = factories.game.create(id=1111, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META11")
        report_match_fake = stub(rest.castlog, "report_match")
        decoy.when(await report_match_fake(payload=ANY), ignore_extra_args=True).then_return(None)

        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META11"},
            json={"source": "convoke"},
        )

        assert resp.status == 200
        assert await resp.json() == {"result": {"success": True}}

    async def test_game_metadata_stores_castlog_link(
        self,
        client: ClientSession,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild = factories.guild.create(xid=2112, name="guild")
        channel = factories.channel.create(xid=3112, name="channel", guild=guild)
        game = factories.game.create(id=1112, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META12")
        report_match_fake = stub(rest.castlog, "report_match")
        decoy.when(await report_match_fake(payload=ANY), ignore_extra_args=True).then_return(
            {
                "match_id": "abc-123",
                "castlog_url": "https://app.castlog.gg/match/abc-123",
                "linked_players": ["ravepool"],
                "unlinked_players": [],
            }
        )

        report = {
            "source": "convoke",
            "links": {"mythic_track": "https://mythictrack.com/g/abc"},
        }
        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META12"},
            json=report,
        )
        assert resp.status == 200

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"]["links"] == {
            "mythic_track": "https://mythictrack.com/g/abc",
            "castlog": "https://app.castlog.gg/match/abc-123",
        }

    async def test_game_metadata_ignores_non_url_castlog_link(
        self,
        client: ClientSession,
        factories: Factories,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        guild = factories.guild.create(xid=2113, name="guild")
        channel = factories.channel.create(xid=3113, name="channel", guild=guild)
        game = factories.game.create(id=1113, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META13")
        report_match_fake = stub(rest.castlog, "report_match")
        decoy.when(await report_match_fake(payload=ANY), ignore_extra_args=True).then_return(
            {"match_id": "abc-123"}
        )

        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META13"},
            json={"source": "convoke"},
        )
        assert resp.status == 200

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert "links" not in detail["metadata"]

    async def test_game_metadata_replaces_prior_report(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2102, name="guild")
        channel = factories.channel.create(xid=3102, name="channel", guild=guild)
        game = factories.game.create(id=1102, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META2")

        first = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META2"},
            json={"source": "convoke", "turns": 5},
        )
        assert first.status == 200
        second = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META2"},
            json={"source": "convoke", "turns": 9},
        )
        assert second.status == 200

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"] == {"source": "convoke", "turns": 9}

    async def test_game_metadata_not_found(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        factories.token.create(key="META3")
        resp = await client.post(
            "/api/game/99999/metadata",
            headers={"Authorization": "Bearer META3"},
            json={"source": "convoke"},
        )
        assert resp.status == 404
        assert (await resp.json())["error"] == "Game not found"

    async def test_game_metadata_invalid_game_id(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        factories.token.create(key="META4")
        resp = await client.post(
            "/api/game/not-a-number/metadata",
            headers={"Authorization": "Bearer META4"},
            json={"source": "convoke"},
        )
        assert resp.status == 400
        assert (await resp.json())["error"] == "Invalid game ID"

    async def test_game_metadata_non_object_body(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2103, name="guild")
        channel = factories.channel.create(xid=3103, name="channel", guild=guild)
        game = factories.game.create(id=1103, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META5")
        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META5"},
            json=["not", "an", "object"],
        )
        assert resp.status == 400
        assert (await resp.json())["error"] == "Metadata must be a JSON object"

    async def test_game_metadata_invalid_json_body(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2109, name="guild")
        channel = factories.channel.create(xid=3109, name="channel", guild=guild)
        game = factories.game.create(id=1109, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META_BADJSON")
        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={
                "Authorization": "Bearer META_BADJSON",
                "Content-Type": "application/json",
            },
            data="{not valid json",
        )
        assert resp.status == 400
        assert (await resp.json())["error"] == "Invalid JSON body"

    async def test_game_metadata_requires_auth(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2104, name="guild")
        channel = factories.channel.create(xid=3104, name="channel", guild=guild)
        game = factories.game.create(id=1104, seats=2, guild=guild, channel=channel)
        resp = await client.post(f"/api/game/{game.id}/metadata", json={"source": "convoke"})
        assert resp.status == 401

    async def test_game_metadata_ignores_older_report(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2105, name="guild")
        channel = factories.channel.create(xid=3105, name="channel", guild=guild)
        game = factories.game.create(id=1105, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META_TS")

        newer = {"source": "convoke", "reported_at": "2026-07-11T18:30:00+00:00", "turns": 20}
        older = {"source": "convoke", "reported_at": "2026-07-11T18:00:00+00:00", "turns": 5}

        r1 = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_TS"},
            json=newer,
        )
        assert r1.status == 200
        # A strictly-older report is accepted (200) but must not clobber the newer one.
        r2 = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_TS"},
            json=older,
        )
        assert r2.status == 200
        assert await r2.json() == {"result": {"success": True}}

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"] == newer

    async def test_game_metadata_concurrent_writes_newer_wins(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        """The locked compare-and-set must land the newer report for either commit order."""
        import asyncio  # allow_inline

        guild = factories.guild.create(xid=2108, name="guild")
        channel = factories.channel.create(xid=3108, name="channel", guild=guild)
        game = factories.game.create(id=1108, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META_RACE")

        newer = {"source": "convoke", "reported_at": "2026-07-11T18:30:00+00:00", "turns": 20}
        older = {"source": "convoke", "reported_at": "2026-07-11T18:00:00+00:00", "turns": 5}
        headers = {"Authorization": "Bearer META_RACE"}

        r_new, r_old = await asyncio.gather(
            client.post(f"/api/game/{game.id}/metadata", headers=headers, json=newer),
            client.post(f"/api/game/{game.id}/metadata", headers=headers, json=older),
        )
        assert r_new.status == 200
        assert r_old.status == 200

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"] == newer

    async def test_game_metadata_drops_unsafe_links(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2106, name="guild")
        channel = factories.channel.create(xid=3106, name="channel", guild=guild)
        game = factories.game.create(id=1106, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META_LINKS")

        resp = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_LINKS"},
            json={
                "source": "convoke",
                "links": {
                    "mythic_track": "https://mythictrack.com/g/abc",
                    "evil": "javascript:alert(document.cookie)",
                    "sneaky": "data:text/html,<script>alert(1)</script>",
                    "not_a_string": 42,
                },
            },
        )
        assert resp.status == 200

        from spellbot import services  # allow_inline

        detail = await services.games.game_detail_view(game.id)
        assert detail is not None
        assert detail["metadata"]["links"] == {"mythic_track": "https://mythictrack.com/g/abc"}

    async def test_game_metadata_rejects_oversized_collections(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=2107, name="guild")
        channel = factories.channel.create(xid=3107, name="channel", guild=guild)
        game = factories.game.create(id=1107, seats=2, guild=guild, channel=channel)
        factories.token.create(key="META_BIG")

        too_many_players = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_BIG"},
            json={"players": [{"name": f"p{i}"} for i in range(65)]},
        )
        assert too_many_players.status == 400
        assert (await too_many_players.json())["error"] == "too many players"

        bad_players = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_BIG"},
            json={"players": "not-a-list"},
        )
        assert bad_players.status == 400
        assert (await bad_players.json())["error"] == "players must be a list"

        bad_links = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_BIG"},
            json={"links": ["not", "an", "object"]},
        )
        assert bad_links.status == 400
        assert (await bad_links.json())["error"] == "links must be an object"

        too_many_links = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_BIG"},
            json={"links": {f"k{i}": "https://x" for i in range(33)}},
        )
        assert too_many_links.status == 400
        assert (await too_many_links.json())["error"] == "too many links"

        bad_ts = await client.post(
            f"/api/game/{game.id}/metadata",
            headers={"Authorization": "Bearer META_BIG"},
            json={"reported_at": "not-a-timestamp"},
        )
        assert bad_ts.status == 400
        assert (await bad_ts.json())["error"] == "invalid reported_at"
