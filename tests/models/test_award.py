from tests.fixtures import Factories


class TestModelAward:
    def test_award(self, factories: Factories):
        guild = factories.guild.create()
        guild_award = factories.guild_award.create(guild=guild)

        assert guild_award.to_dict() == {
            "id": guild_award.id,
            "guild_xid": guild_award.guild_xid,
            "count": guild_award.count,
            "repeating": guild_award.repeating,
            "role": guild_award.role,
            "message": guild_award.message,
        }
