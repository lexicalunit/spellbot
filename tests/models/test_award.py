from tests.factories.award import GuildAwardFactory
from tests.factories.guild import GuildFactory


class TestModelAward:
    def test_award(self):
        guild = GuildFactory.create()
        guild_award = GuildAwardFactory.create(guild=guild)

        assert guild_award.to_dict() == {
            "id": guild_award.id,
            "guild_xid": guild_award.guild_xid,
            "count": guild_award.count,
            "repeating": guild_award.repeating,
            "role": guild_award.role,
            "message": guild_award.message,
        }
