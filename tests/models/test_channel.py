from spellbot.database import DatabaseSession
from spellbot.models.channel import Channel
from spellbot.models.guild import Guild


class TestModelChannel:
    def test_channel(self, session):
        guild = Guild(xid=101, name="guild-name")
        channel = Channel(xid=201, name="channel-name", guild=guild)
        DatabaseSession.add_all([guild, channel])
        DatabaseSession.commit()

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
