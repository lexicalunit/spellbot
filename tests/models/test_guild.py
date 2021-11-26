from tests.fixtures import Factories


class TestModelGuild:
    def test_guild(self, factories: Factories):
        guild = factories.guild.create()
        channel1 = factories.channel.create(guild=guild)
        channel2 = factories.channel.create(guild=guild)
        award1 = factories.guild_award.create(count=10, guild=guild)
        award2 = factories.guild_award.create(count=20, guild=guild)

        assert guild.to_dict() == {
            "xid": guild.xid,
            "created_at": guild.created_at,
            "updated_at": guild.updated_at,
            "name": guild.name,
            "motd": guild.motd,
            "show_links": guild.show_links,
            "voice_create": guild.voice_create,
            "show_points": guild.show_points,
            "channels": [channel1.to_dict(), channel2.to_dict()],
            "awards": [award1.to_dict(), award2.to_dict()],
        }
