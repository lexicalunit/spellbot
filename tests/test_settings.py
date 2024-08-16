from __future__ import annotations

import pytest

from spellbot.settings import Settings


class TestSettings:
    @pytest.fixture
    def settings(self) -> Settings:
        return Settings()

    def test_guild_object(self, settings: Settings) -> None:
        settings.DEBUG_GUILD = None
        assert not settings.GUILD_OBJECT

    def test_guild_object_debug(self, settings: Settings) -> None:
        settings.DEBUG_GUILD = "1234"
        obj = settings.GUILD_OBJECT
        assert obj
        assert obj.id == 1234
