from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import GuildData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelGuild:
    def test_guild_to_data(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel1 = factories.channel.create(guild=guild)
        channel2 = factories.channel.create(guild=guild)
        award1 = factories.guild_award.create(count=10, guild=guild)
        award2 = factories.guild_award.create(count=20, guild=guild)

        guild_data = guild.to_data()
        assert isinstance(guild_data, GuildData)
        assert asdict(guild_data) == {
            "awards": [
                asdict(award1.to_data()),
                asdict(award2.to_data()),
            ],
            "banned": guild.banned,
            "channels": [
                asdict(channel1.to_data()),
                asdict(channel2.to_data()),
            ],
            "created_at": guild.created_at,
            "enable_mythic_track": guild.enable_mythic_track,
            "motd": guild.motd,
            "name": guild.name,
            "notice": guild.notice,
            "show_links": guild.show_links,
            "suggest_voice_category": guild.suggest_voice_category,
            "updated_at": guild.updated_at,
            "use_max_bitrate": guild.use_max_bitrate,
            "voice_create": guild.voice_create,
            "xid": guild.xid,
        }
