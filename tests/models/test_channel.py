from __future__ import annotations

from tests.fixtures import Factories


class TestModelChannel:
    def test_channel(self, factories: Factories):
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)

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
            "motd": channel.motd,
            "voice_category": channel.voice_category,
            "delete_expired": channel.delete_expired,
            "show_points": channel.show_points,
        }
