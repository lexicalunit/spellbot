from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import pytz

from spellbot.enums import GameFormat
from spellbot.models import GameStatus

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from freezegun.api import FrozenDateTimeFactory
    from syrupy.assertion import SnapshotAssertion

    from tests.fixtures import Factories


@pytest.mark.asyncio
class TestWebRecord:
    async def test_user_record(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=pytz.utc))
        user1 = factories.user.create(xid=101, name="user:1")
        user2 = factories.user.create(xid=102, name="user@2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid, points=3)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, points=1)
        factories.play.create(game_id=game2.id, user_xid=user1.xid, points=None)
        factories.play.create(game_id=game2.id, user_xid=user2.xid, points=5)
        factories.play.create(game_id=game3.id, user_xid=user1.xid, points=None)
        factories.play.create(game_id=game3.id, user_xid=user2.xid, points=10)

        resp = await client.get(f"/g/{guild.xid}/u/{user1.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_with_cookies(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=pytz.utc))
        user1 = factories.user.create(xid=101, name="user:1")
        user2 = factories.user.create(xid=102, name="user@2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid, points=3)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, points=1)
        factories.play.create(game_id=game2.id, user_xid=user1.xid, points=None)
        factories.play.create(game_id=game2.id, user_xid=user2.xid, points=5)
        factories.play.create(game_id=game3.id, user_xid=user1.xid, points=None)
        factories.play.create(game_id=game3.id, user_xid=user2.xid, points=10)

        resp = await client.get(
            f"/g/{guild.xid}/u/{user1.xid}",
            cookies={
                "timezone_offset": "480",
                "timezone_name": "America/Los_Angeles",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_no_plays(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
    ) -> None:
        user = factories.user.create(xid=101, name="user")
        guild = factories.guild.create(xid=201, name="guild")

        resp = await client.get(f"/g/{guild.xid}/u/{user.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=pytz.utc))
        user1 = factories.user.create(xid=101, name="user1")
        user2 = factories.user.create(xid=102, name="user2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid, points=3)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, points=1)
        factories.play.create(game_id=game2.id, user_xid=user1.xid, points=0)
        factories.play.create(game_id=game2.id, user_xid=user2.xid, points=5)
        factories.play.create(game_id=game3.id, user_xid=user1.xid, points=0)
        factories.play.create(game_id=game3.id, user_xid=user2.xid, points=10)

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_with_cookies(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=pytz.utc))
        user1 = factories.user.create(xid=101, name="user1")
        user2 = factories.user.create(xid=102, name="user2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid, points=3)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, points=1)
        factories.play.create(game_id=game2.id, user_xid=user1.xid, points=0)
        factories.play.create(game_id=game2.id, user_xid=user2.xid, points=5)
        factories.play.create(game_id=game3.id, user_xid=user1.xid, points=0)
        factories.play.create(game_id=game3.id, user_xid=user2.xid, points=10)

        resp = await client.get(
            f"/g/{guild.xid}/c/{channel.xid}",
            cookies={
                "timezone_offset": "480",
                "timezone_name": "America/Los_Angeles",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_with_invalid_cookies(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 1, 1, tzinfo=pytz.utc))
        user1 = factories.user.create(xid=101, name="user1")
        user2 = factories.user.create(xid=102, name="user2")
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        game1 = factories.game.create(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game1, message_xid=901)
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game2, message_xid=902)
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.now(tz=pytz.utc),
            updated_at=datetime.now(tz=pytz.utc),
        )
        factories.post.create(guild=guild, channel=channel, game=game3, message_xid=903)
        factories.play.create(game_id=game1.id, user_xid=user1.xid, points=3)
        factories.play.create(game_id=game1.id, user_xid=user2.xid, points=1)
        factories.play.create(game_id=game2.id, user_xid=user1.xid, points=0)
        factories.play.create(game_id=game2.id, user_xid=user2.xid, points=5)
        factories.play.create(game_id=game3.id, user_xid=user1.xid, points=0)
        factories.play.create(game_id=game3.id, user_xid=user2.xid, points=10)

        resp = await client.get(
            f"/g/{guild.xid}/c/{channel.xid}",
            cookies={
                "timezone_offset": "BUGUS",
                "timezone_name": "America/Los_Angeles",
            },
        )
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_no_plays(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=101, name="channel", guild=guild)

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_invalid_ids(self, client: ClientSession) -> None:
        resp = await client.get("/g/abc/u/xyz")
        assert resp.status == 404

    async def test_channel_record_invalid_ids(self, client: ClientSession) -> None:
        resp = await client.get("/g/abc/c/xyz")
        assert resp.status == 404

    async def test_user_record_missing_guild(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        user = factories.user.create(xid=101, name="user")
        resp = await client.get(f"/g/404/u/{user.xid}")
        assert resp.status == 404

    async def test_channel_record_missing_guild(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild)
        resp = await client.get(f"/g/404/c/{channel.xid}")
        assert resp.status == 404

    async def test_channel_record_missing_channel(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await client.get(f"/g/{guild.xid}/c/404")
        assert resp.status == 404
