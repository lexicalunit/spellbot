from tests.factories.channel import ChannelFactory
from tests.factories.guild import GuildFactory


class TestModelChannel:
    def test_channel(self):
        guild = GuildFactory.create()
        channel = ChannelFactory.create(guild=guild)

        assert channel.to_dict() == {
            "xid": channel.xid,
            "created_at": channel.created_at,
            "updated_at": channel.updated_at,
            "guild_xid": channel.guild_xid,
            "name": channel.name,
            "default_seats": channel.default_seats,
            "auto_verify": channel.auto_verify,
            "unverified_only": channel.unverified_only,
            "verified_only": channel.verified_only,
        }
