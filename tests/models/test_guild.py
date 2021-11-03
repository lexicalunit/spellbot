from tests.factories.award import GuildAwardFactory
from tests.factories.channel import ChannelFactory
from tests.factories.guild import GuildFactory


class TestModelGuild:
    def test_guild(self):
        guild = GuildFactory.create()
        channel1 = ChannelFactory.create(guild=guild)
        channel2 = ChannelFactory.create(guild=guild)
        award1 = GuildAwardFactory.create(count=10, guild=guild)
        award2 = GuildAwardFactory.create(count=20, guild=guild)

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
            "channels": [channel1.to_dict(), channel2.to_dict()],
            "awards": [award1.to_dict(), award2.to_dict()],
        }
