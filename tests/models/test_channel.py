from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameBracket, GameFormat, GameService

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelChannel:
    def test_channel(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)

        assert channel.to_dict() == {
            "xid": channel.xid,
            "created_at": channel.created_at,
            "updated_at": channel.updated_at,
            "guild_xid": channel.guild_xid,
            "name": channel.name,
            "default_seats": channel.default_seats,
            "default_format": GameFormat(channel.default_format),
            "default_bracket": GameBracket(channel.default_bracket),
            "default_service": GameService(channel.default_service),
            "auto_verify": channel.auto_verify,
            "unverified_only": channel.unverified_only,
            "verified_only": channel.verified_only,
            "motd": channel.motd,
            "extra": channel.extra,
            "voice_category": channel.voice_category,
            "voice_invite": channel.voice_invite,
            "delete_expired": channel.delete_expired,
            "blind_games": channel.blind_games,
        }
