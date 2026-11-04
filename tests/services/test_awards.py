# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.models import GuildAward
from spellbot.services import NewAward, awards

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
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: [NewAward(role="one", message="msg", remove=False)]}
        game2 = factories.game.create(guild=guild, channel=channel)
        factories.play.create(user_xid=user.xid, game_id=game2.id)
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {user.xid: [NewAward(role="one", message="msg", remove=False)]}

    async def test_give_awards_no_user_award(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        factories.guild_award.create(guild=guild, count=1, role="one", message="msg")
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create()
        factories.play.create(user_xid=user.xid, game_id=game.id)
        # Note: no user_award created for this user
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        assert give_outs == {}

    async def test_give_awards_already_has_non_repeating_award(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        # Create a non-repeating award
        guild_award = factories.guild_award.create(
            guild=guild,
            count=1,
            role="one",
            message="msg",
            repeating=False,
        )
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create()
        factories.play.create(user_xid=user.xid, game_id=game.id)
        # User already has this award
        factories.user_award.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
            guild_award_id=guild_award.id,
        )
        give_outs = await awards.give_awards(guild_xid=guild.xid, player_xids=[user.xid])
        # Award should not be given again because it's non-repeating and already earned
        assert give_outs == {}

    async def test_give_awards_to_several_players(
        self,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        factories.guild_award.create(guild=guild, count=1, role="one", message="first")
        factories.guild_award.create(guild=guild, count=2, role="two", message="second")
        veteran, newcomer, no_award_row = (factories.user.create() for _ in range(3))
        for user, games_played in ((veteran, 2), (newcomer, 1), (no_award_row, 1)):
            for _ in range(games_played):
                game = factories.game.create(guild=guild, channel=channel)
                factories.play.create(user_xid=user.xid, game_id=game.id)
        for user in (veteran, newcomer):
            factories.user_award.create(user_xid=user.xid, guild_xid=guild.xid, guild_award_id=None)

        give_outs = await awards.give_awards(
            guild_xid=guild.xid,
            player_xids=[veteran.xid, newcomer.xid, no_award_row.xid],
        )
        assert give_outs == {
            veteran.xid: [NewAward(role="two", message="second", remove=False)],
            newcomer.xid: [NewAward(role="one", message="first", remove=False)],
        }


class TestEarns:
    @pytest.mark.parametrize(
        ("count", "repeating", "plays", "expected"),
        [
            pytest.param(5, False, 5, True, id="at-count"),
            pytest.param(5, False, 10, False, id="past-count"),
            pytest.param(5, True, 10, True, id="repeating-multiple"),
            pytest.param(5, True, 7, False, id="repeating-not-multiple"),
            pytest.param(0, True, 7, False, id="zero-count"),
        ],
    )
    def test_earns(self, count: int, repeating: bool, plays: int, expected: bool) -> None:
        award = GuildAward(guild_xid=1, count=count, repeating=repeating, role="r", message="m")
        assert awards.earns(award, plays) is expected
