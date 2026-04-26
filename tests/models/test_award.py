from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import GuildAwardData, UserAwardData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelAward:
    def test_guild_award_to_data(self, factories: Factories) -> None:
        guild = factories.guild.create()
        guild_award = factories.guild_award.create(guild=guild)

        award_data = guild_award.to_data()
        assert isinstance(award_data, GuildAwardData)
        assert asdict(award_data) == {
            "id": guild_award.id,
            "guild_xid": guild_award.guild_xid,
            "count": guild_award.count,
            "repeating": guild_award.repeating,
            "remove": guild_award.remove,
            "role": guild_award.role,
            "message": guild_award.message,
            "unverified_only": guild_award.unverified_only,
            "verified_only": guild_award.verified_only,
        }

    def test_user_award_to_data(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        guild_award = factories.guild_award.create(guild=guild)
        user_award = factories.user_award.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            guild_award_id=guild_award.id,
        )

        award_data = user_award.to_data()
        assert isinstance(award_data, UserAwardData)
        assert asdict(award_data) == {
            "user_xid": user_award.user_xid,
            "guild_xid": user_award.guild_xid,
            "guild_award_id": user_award.guild_award_id,
        }
