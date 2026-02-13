from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp
import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.web.api.rest import (
    delete_message,
    game_record_embed,
    post_with_retry,
    reply,
    retry_if_not_unrecoverable,
    send_dm,
    send_message,
    update_message,
)

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from freezegun.api import FrozenDateTimeFactory
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestWebRecord:
    async def test_user_record(  # noqa: PLR0915
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

        # bad authentication with rate limiting
        mocker.patch("spellbot.web.builder.rate_limited", return_value=True)
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": "Bearer BOGUS"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Too many requests"}

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

        # Test rate limiting on failed verification
        mocker.patch(
            "spellbot.services.plays.PlaysService.verify_game_pin",
            return_value=False,
        )
        mocker.patch("spellbot.web.api.rest.rate_limited", return_value=True)
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}

        # Test rate limiting on ValueError
        mocker.patch("spellbot.web.api.rest.rate_limited", return_value=True)
        resp = await client.post(
            "/api/game/FOO/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}

        # Test rate limiting on KeyError
        mocker.patch("spellbot.web.api.rest.rate_limited", return_value=True)
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}

        # Test rate limiting on Exception
        mocker.patch(
            "spellbot.services.plays.PlaysService.verify_game_pin",
            side_effect=Exception("BOOM"),
        )
        mocker.patch("spellbot.web.api.rest.rate_limited", return_value=True)
        resp = await client.post(
            f"/api/game/{game.id}/verify",
            headers={"Authorization": f"Bearer {token.key}"},
            json={"user_xid": user1.xid, "guild_xid": guild.xid, "pin": "A"},
        )
        assert resp.status == 429
        assert await resp.json() == {"error": "Rate limited"}


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
    def test_client_response_error(self, status: int, expected: bool) -> None:
        exc = aiohttp.ClientResponseError(None, None, status=status)  # type: ignore[arg-type]
        assert retry_if_not_unrecoverable(exc) is expected

    def test_non_client_response_error(self) -> None:
        exc = ValueError("Some error")
        assert retry_if_not_unrecoverable(exc) is True


@pytest.mark.asyncio
class TestPostWithRetry:
    async def test_post_with_retry_success(self, mocker: MockerFixture) -> None:
        """Test post_with_retry makes correct API call and returns response."""
        mock_response = mocker.MagicMock()
        mock_response.raise_for_status = mocker.MagicMock()
        mock_response.json = mocker.AsyncMock(return_value={"id": "12345"})
        mock_response.__aenter__ = mocker.AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = mocker.AsyncMock(return_value=None)

        mock_session = mocker.MagicMock()
        mock_session.post = mocker.MagicMock(return_value=mock_response)

        result = await post_with_retry(mock_session, "/test/path", {"key": "value"})
        assert result == {"id": "12345"}
        mock_session.post.assert_called_once()

    async def test_post_with_retry_get_method(self, mocker: MockerFixture) -> None:
        """Test post_with_retry with GET method."""
        mock_response = mocker.MagicMock()
        mock_response.raise_for_status = mocker.MagicMock()
        mock_response.json = mocker.AsyncMock(return_value={"data": "test"})
        mock_response.__aenter__ = mocker.AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = mocker.AsyncMock(return_value=None)

        mock_session = mocker.MagicMock()
        mock_session.get = mocker.MagicMock(return_value=mock_response)

        result = await post_with_retry(mock_session, "/test/path", method="get")
        assert result == {"data": "test"}
        mock_session.get.assert_called_once()


class TestGameRecordEmbed:
    def test_with_winner(self) -> None:
        game = {
            "id": 1,
            "guild_xid": 123,
            "channel_xid": 456,
            "started_at": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            "jump_links": {123: "https://discord.com/jump/123/456/789"},
        }
        players = [
            {"xid": 101, "name": "Player1"},
            {"xid": 102, "name": "Player2"},
        ]
        commanders: dict[int | None, str] = {101: "Atraxa", 102: "Kenrith"}
        result = game_record_embed(
            game=game,  # type: ignore[arg-type]
            players=players,  # type: ignore[arg-type]
            commanders=commanders,
            winner_xid=101,
            tracker_xid=102,
        )
        assert "embeds" in result
        assert "🎉 Winner 🎉" in str(result)
        assert "Atraxa" in str(result)

    def test_without_winner(self) -> None:
        game = {
            "id": 1,
            "guild_xid": 123,
            "channel_xid": 456,
            "started_at": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            "jump_links": {123: "https://discord.com/jump/123/456/789"},
        }
        players = [
            {"xid": 101, "name": "Player1"},
            {"xid": 102, "name": "Player2"},
        ]
        commanders: dict[int | None, str] = {101: "Atraxa", 102: "Kenrith"}
        result = game_record_embed(
            game=game,  # type: ignore[arg-type]
            players=players,  # type: ignore[arg-type]
            commanders=commanders,
            winner_xid=None,
            tracker_xid=102,
        )
        assert "embeds" in result
        assert "No Winner" in str(result)
        assert "Draw game" in str(result)


@pytest.mark.asyncio
class TestSendMessage:
    async def test_send_message_success(self, mocker: MockerFixture) -> None:
        mock_post = mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            return_value={"id": "12345"},
        )
        result = await send_message(123, {"content": "Hello"})
        assert result == {"id": "12345"}
        mock_post.assert_called_once()

    async def test_send_message_failure(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            side_effect=Exception("Connection error"),
        )
        result = await send_message(123, {"content": "Hello"})
        assert result is None


@pytest.mark.asyncio
class TestSendDm:
    async def test_send_dm_success(self, mocker: MockerFixture) -> None:
        mock_post = mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            side_effect=[{"id": "channel123"}, {"id": "message456"}],
        )
        await send_dm(101, {"content": "Hello"})
        assert mock_post.call_count == 2

    async def test_send_dm_unrecoverable_error(self, mocker: MockerFixture) -> None:
        exc = aiohttp.ClientResponseError(None, None, status=403)  # type: ignore[arg-type]
        mocker.patch("spellbot.web.api.rest.post_with_retry", side_effect=exc)
        # Should not raise, just log
        await send_dm(101, {"content": "Hello"})

    async def test_send_dm_recoverable_client_error(self, mocker: MockerFixture) -> None:
        # 500 is not in UNRECOVERABLE, so it should be re-raised and caught by outer except
        exc = aiohttp.ClientResponseError(None, None, status=500)  # type: ignore[arg-type]
        mocker.patch("spellbot.web.api.rest.post_with_retry", side_effect=exc)
        # Should not raise, just log
        await send_dm(101, {"content": "Hello"})

    async def test_send_dm_other_exception(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            side_effect=Exception("Network error"),
        )
        # Should not raise, just log
        await send_dm(101, {"content": "Hello"})


@pytest.mark.asyncio
class TestUpdateMessage:
    async def test_update_message_success(self, mocker: MockerFixture) -> None:
        mock_post = mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            return_value={"id": "12345"},
        )
        result = await update_message(123, 456, {"content": "Updated"})
        assert result == {"id": "12345"}
        mock_post.assert_called_once()

    async def test_update_message_failure(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            side_effect=Exception("Connection error"),
        )
        result = await update_message(123, 456, {"content": "Updated"})
        assert result is None


@pytest.mark.asyncio
class TestDeleteMessage:
    async def test_delete_message_success(self, mocker: MockerFixture) -> None:
        mock_post = mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            return_value={},
        )
        result = await delete_message(123, 456)
        assert result == {}
        mock_post.assert_called_once()

    async def test_delete_message_failure(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "spellbot.web.api.rest.post_with_retry",
            side_effect=Exception("Connection error"),
        )
        result = await delete_message(123, 456)
        assert result is None


@pytest.mark.asyncio
class TestGameRecordEndpoint:
    async def test_game_record_success(
        self,
        client: ClientSession,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
        mocker: MockerFixture,
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
        token = factories.token.create(key="RECORD1")

        mocker.patch("spellbot.web.api.rest.send_dm", return_value=None)

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": f"Bearer {token.key}"},
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
        token = factories.token.create(key="RECORD2")

        resp = await client.post(
            "/api/game/99999/record",
            headers={"Authorization": f"Bearer {token.key}"},
            json={
                "winner": 101,
                "tracker": 102,
                "players": [{"xid": 101, "commander": "Atraxa"}],
            },
        )
        assert resp.status == 404
        data = await resp.json()
        assert data["error"] == "Game not found"

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
        token = factories.token.create(key="RECORD3")

        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": f"Bearer {token.key}"},
            json={
                "winner": 101,
                "tracker": 102,
                "players": [],
            },
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["error"] == "No players provided"

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
        token = factories.token.create(key="RECORD4")

        # Provide 2 players but only 1 play exists
        resp = await client.post(
            f"/api/game/{game.id}/record",
            headers={"Authorization": f"Bearer {token.key}"},
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
        assert data["error"] == "Mismatched player count"
