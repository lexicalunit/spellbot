# Copyright (c) 2026 spellbot@lexicalunit.com

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

        guild_data = GuildData.from_model(guild)
        assert isinstance(guild_data, GuildData)
        assert asdict(guild_data) == {
            "banned": guild.banned,
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
            "active": guild.active,
            "locale": guild.locale,
            "icon": guild.icon,
            "promote": guild.promote,
            "show_convoke_guild": guild.show_convoke_guild,
            "xid": guild.xid,
        }
