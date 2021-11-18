from datetime import datetime

from aiohttp.client import ClientSession
from syrupy.assertion import SnapshotAssertion

from spellbot.models import GameFormat, GameStatus
from tests.fixtures import Factories


class TestWebRecord:
    async def test_user_record(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
        freezer,
    ):
        freezer.move_to(datetime(2020, 1, 1))
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
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_xid=901,
        )
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_xid=902,
        )
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message_xid=903,
        )
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

    async def test_user_record_no_plays(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
    ):
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
        freezer,
    ):
        freezer.move_to(datetime(2020, 1, 1))
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
            message_xid=901,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        game2 = factories.game.create(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            message_xid=902,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        game3 = factories.game.create(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            message_xid=903,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
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

    async def test_channel_record_no_plays(
        self,
        client: ClientSession,
        snapshot: SnapshotAssertion,
        factories: Factories,
    ):
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=101, name="channel", guild=guild)

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_invalid_ids(self, client: ClientSession):
        resp = await client.get("/g/abc/u/xyz")
        assert resp.status == 404

    async def test_channel_record_invalid_ids(self, client: ClientSession):
        resp = await client.get("/g/abc/c/xyz")
        assert resp.status == 404
