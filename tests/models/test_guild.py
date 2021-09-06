from spellbot.database import DatabaseSession
from spellbot.models.award import GuildAward
from spellbot.models.channel import Channel
from spellbot.models.guild import Guild


class TestModelGuild:
    def test_guild(self, session):
        guild = Guild(xid=101, name="guild-name")
        channel1 = Channel(xid=201, name="channel1", guild=guild)
        channel2 = Channel(xid=202, name="channel2", guild=guild)
        guild_award1 = GuildAward(
            count=10,
            role="a-role",
            message="a-message",
            guild=guild,
        )
        guild_award2 = GuildAward(
            count=20,
            role="b-role",
            message="b-message",
            guild=guild,
        )
        DatabaseSession.add_all([guild, channel1, channel2, guild_award1, guild_award2])
        DatabaseSession.commit()

        assert guild.to_dict() == {
            "xid": guild.xid,
            "created_at": guild.created_at,
            "updated_at": guild.updated_at,
            "name": guild.name,
            "motd": guild.motd,
            "show_links": guild.show_links,
            "voice_create": guild.voice_create,
            "show_points": guild.show_points,
            "legacy_prefix": guild.legacy_prefix,
            "channels": [channel.to_dict() for channel in guild.channels],
            "awards": [award.to_dict() for award in guild.awards],
        }
