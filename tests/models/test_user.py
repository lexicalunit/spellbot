from spellbot.database import DatabaseSession
from spellbot.models.channel import Channel
from spellbot.models.game import Game, GameStatus
from spellbot.models.guild import Guild
from spellbot.models.play import Play
from spellbot.models.user import User


class TestModelUser:
    def test_user(self, session):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        game1 = Game(message_xid=301, seats=4, guild=guild, channel=channel)
        user1 = User(xid=11, name="user1")
        user2 = User(xid=12, name="user2", game=game1)
        game2 = Game(
            message_xid=301,
            seats=2,
            status=GameStatus.STARTED.value,
            guild=guild,
            channel=channel,
        )
        DatabaseSession.add_all([guild, channel, game1, game2, user1, user2])
        DatabaseSession.commit()

        player1 = User(xid=21, name="player1", game=game2)
        player2 = User(xid=22, name="player2", game=game2)
        play1 = Play(user_xid=player1.xid, game_id=game2.id, points=5)
        play2 = Play(user_xid=player2.xid, game_id=game2.id, points=1)
        DatabaseSession.add_all([player1, player2, play1, play2])
        DatabaseSession.commit()

        assert user1.points(1) is None
        assert not user1.waiting
        assert user1.to_dict() == {
            "xid": user1.xid,
            "created_at": user1.created_at,
            "updated_at": user1.updated_at,
            "name": user1.name,
            "banned": user1.banned,
            "game_id": user1.game_id,
        }
        assert user2.waiting
        assert user2.to_dict() == {
            "xid": user2.xid,
            "created_at": user2.created_at,
            "updated_at": user2.updated_at,
            "name": user2.name,
            "banned": user2.banned,
            "game_id": game1.id,
        }
        assert player1.points(game2.id) == play1.points
        assert player2.points(game2.id) == play2.points
