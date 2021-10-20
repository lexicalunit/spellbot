from spellbot.database import DatabaseSession
from spellbot.models.award import GuildAward
from spellbot.models.guild import Guild


class TestModelAward:
    def test_award(self):
        guild = Guild(xid=101, name="guild-name")
        guild_award = GuildAward(
            count=10,
            role="a-role",
            message="a-message",
            guild=guild,
        )
        DatabaseSession.add_all([guild, guild_award])
        DatabaseSession.commit()

        assert guild_award.to_dict() == {
            "id": guild_award.id,
            "guild_xid": guild_award.guild_xid,
            "count": guild_award.count,
            "repeating": guild_award.repeating,
            "role": guild_award.role,
            "message": guild_award.message,
        }
