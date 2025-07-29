from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.services import AwardsService, NewAward

if TYPE_CHECKING:
    from spellbot.models import Channel, Guild
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceAwards:
    async def test_give_awards_first_award(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        factories.guild_award.create(guild=guild, count=1, role="one", message="msg")
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create()
        factories.play.create(user_xid=user.xid, game_id=game.id)
        factories.user_award.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: [NewAward(role="one", message="msg", remove=False)]}

    async def test_give_awards_when_plays_from_different_server(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        factories.guild_award.create(guild=guild, count=1, role="one", message="msg")
        factories.user_award.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )

        other_guild = factories.guild.create(xid=guild.xid + 1)
        other_channel = factories.channel.create(xid=channel.xid + 1, guild=other_guild)
        other_game = factories.game.create(guild=other_guild, channel=other_channel)
        factories.play.create(user_xid=user.xid, game_id=other_game.id)

        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {}

    async def test_give_awards_no_plays(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        game = factories.game.create(guild=guild, channel=channel)
        factories.guild_award.create(guild=guild, count=1, role="one", message="msg")
        user = factories.user.create(game=game)
        factories.user_award.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {}

    async def test_give_awards_needs_more_plays(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        factories.guild_award.create(guild=guild, count=2, role="two", message="msg")
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create()
        factories.play.create(user_xid=user.xid, game_id=game.id)
        factories.user_award.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {}

    async def test_give_awards_repeating(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        factories.guild_award.create(
            guild=guild,
            count=1,
            role="one",
            message="msg",
            repeating=True,
        )
        game1 = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create()
        factories.play.create(user_xid=user.xid, game_id=game1.id)
        factories.user_award.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=None,
        )
        awards = AwardsService()
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: [NewAward(role="one", message="msg", remove=False)]}
        game2 = factories.game.create(guild=guild, channel=channel)
        factories.play.create(user_xid=user.xid, game_id=game2.id)
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: [NewAward(role="one", message="msg", remove=False)]}
