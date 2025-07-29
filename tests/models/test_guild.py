from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelGuild:
    def test_guild(self, factories: Factories) -> None:
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
            "use_max_bitrate": guild.use_max_bitrate,
            "channels": sorted(
                [channel1.to_dict(), channel2.to_dict()],
                key=lambda c: c["xid"],
            ),
            "awards": sorted(
                [award1.to_dict(), award2.to_dict()],
                key=lambda c: c["id"],
            ),
            "banned": guild.banned,
            "notice": guild.notice,
            "suggest_voice_category": guild.suggest_voice_category,
            "enable_mythic_track": guild.enable_mythic_track,
        }
