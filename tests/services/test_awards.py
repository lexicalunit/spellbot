import pytest

from spellbot.database import DatabaseSession
from spellbot.services.awards import AwardsService, NewAward
from tests.factories.award import GuildAwardFactory, UserAwardFactory
from tests.factories.game import GameFactory
from tests.factories.play import PlayFactory
from tests.factories.user import UserFactory


@pytest.mark.asyncio
class TestServiceAwards:
    async def test_give_awards_first_award(self, guild, channel):
        GuildAwardFactory.create(guild=guild, count=1, role="one", message="msg")
        game = GameFactory.create(guild=guild, channel=channel)
        user = UserFactory.create()
        DatabaseSession.commit()

        PlayFactory.create(user_xid=user.xid, game_id=game.id)
        UserAwardFactory.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        DatabaseSession.commit()

        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: NewAward(role="one", message="msg")}

    async def test_give_awards_no_plays(self, guild, channel):
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()

        GuildAwardFactory.create(guild=guild, count=1, role="one", message="msg")
        user = UserFactory.create(game=game)
        DatabaseSession.commit()

        UserAwardFactory.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        DatabaseSession.commit()

        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {}

    async def test_give_awards_needs_more_plays(self, guild, channel):
        GuildAwardFactory.create(guild=guild, count=2, role="two", message="msg")
        game = GameFactory.create(guild=guild, channel=channel)
        user = UserFactory.create()
        DatabaseSession.commit()

        PlayFactory.create(user_xid=user.xid, game_id=game.id)
        UserAwardFactory.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        DatabaseSession.commit()

        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {}

    async def test_give_awards_repeating(self, guild, channel):
        GuildAwardFactory.create(
            guild=guild,
            count=1,
            role="one",
            message="msg",
            repeating=True,
        )
        game1 = GameFactory.create(guild=guild, channel=channel)
        user = UserFactory.create()
        DatabaseSession.commit()

        PlayFactory.create(user_xid=user.xid, game_id=game1.id)
        UserAwardFactory.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        DatabaseSession.commit()

        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: NewAward(role="one", message="msg")}

        game2 = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()
        PlayFactory.create(user_xid=user.xid, game_id=game2.id)
        DatabaseSession.commit()

        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: NewAward(role="one", message="msg")}
