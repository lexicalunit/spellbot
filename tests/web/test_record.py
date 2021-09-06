from datetime import datetime

from spellbot.database import DatabaseSession
from spellbot.models.channel import Channel
from spellbot.models.game import Game, GameFormat, GameStatus
from spellbot.models.guild import Guild
from spellbot.models.play import Play
from spellbot.models.user import User


class TestWebRecord:
    async def test_user_record(self, session, client, snapshot, freezer):
        freezer.move_to(datetime(2020, 1, 1))
        user1 = User(xid=101, name="user1")
        user2 = User(xid=102, name="user2")
        guild = Guild(xid=201, name="guild")
        channel = Channel(xid=301, name="channel", guild=guild)
        game1 = Game(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        game2 = Game(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        game3 = Game(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        DatabaseSession.add_all([user1, user2, guild, channel, game1, game2, game3])
        DatabaseSession.commit()
        play1_1 = Play(game_id=game1.id, user_xid=user1.xid, points=3)
        play1_2 = Play(game_id=game1.id, user_xid=user2.xid, points=1)
        play2_1 = Play(game_id=game2.id, user_xid=user1.xid)
        play2_2 = Play(game_id=game2.id, user_xid=user2.xid, points=5)
        play3_1 = Play(game_id=game3.id, user_xid=user1.xid)
        play3_2 = Play(game_id=game3.id, user_xid=user2.xid, points=10)
        DatabaseSession.add_all([play1_1, play1_2, play2_1, play2_2, play3_1, play3_2])
        DatabaseSession.commit()

        resp = await client.get(f"/g/{guild.xid}/u/{user1.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_no_plays(self, session, client, snapshot):
        user = User(xid=101, name="user")
        guild = Guild(xid=201, name="guild")
        DatabaseSession.add_all([user, guild])
        DatabaseSession.commit()

        resp = await client.get(f"/g/{guild.xid}/u/{user.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record(self, session, client, snapshot, freezer):
        freezer.move_to(datetime(2020, 1, 1))
        user1 = User(xid=101, name="user1")
        user2 = User(xid=102, name="user2")
        guild = Guild(xid=201, name="guild")
        channel = Channel(xid=301, name="channel", guild=guild)
        game1 = Game(
            id=1,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.MODERN.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        game2 = Game(
            id=2,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.STANDARD.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        game3 = Game(
            id=3,
            seats=2,
            status=GameStatus.STARTED.value,
            format=GameFormat.LEGACY.value,
            guild=guild,
            channel=channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        DatabaseSession.add_all([user1, user2, guild, channel, game1, game2, game3])
        DatabaseSession.commit()
        play1_1 = Play(game_id=game1.id, user_xid=user1.xid, points=3)
        play1_2 = Play(game_id=game1.id, user_xid=user2.xid, points=1)
        play2_1 = Play(game_id=game2.id, user_xid=user1.xid)
        play2_2 = Play(game_id=game2.id, user_xid=user2.xid, points=5)
        play3_1 = Play(game_id=game3.id, user_xid=user1.xid)
        play3_2 = Play(game_id=game3.id, user_xid=user2.xid, points=10)
        DatabaseSession.add_all([play1_1, play1_2, play2_1, play2_2, play3_1, play3_2])
        DatabaseSession.commit()

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_channel_record_no_plays(self, session, client, snapshot):
        guild = Guild(xid=201, name="guild")
        channel = Channel(xid=101, name="channel", guild=guild)
        DatabaseSession.add_all([channel, guild])
        DatabaseSession.commit()

        resp = await client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert resp.status == 200
        text = await resp.text()
        assert text == snapshot

    async def test_user_record_invalid_ids(self, client):
        resp = await client.get("/g/abc/u/xyz")
        assert resp.status == 404

    async def test_channel_record_invalid_ids(self, client):
        resp = await client.get("/g/abc/c/xyz")
        assert resp.status == 404
