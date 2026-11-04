# Copyright (c) 2026 spellbot@lexicalunit.com

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

    def test_require_passes_when_set(self, settings: Settings) -> None:
        settings.SECRET_TOKEN = "secret"
        settings.SESSION_SECRET_KEY = "key"
        settings.require("SECRET_TOKEN", "SESSION_SECRET_KEY")

    def test_require_exits_when_unset(self, settings: Settings) -> None:
        settings.SECRET_TOKEN = None
        settings.SESSION_SECRET_KEY = ""
        with pytest.raises(SystemExit, match="SECRET_TOKEN, SESSION_SECRET_KEY"):
            settings.require("SECRET_TOKEN", "SESSION_SECRET_KEY")

    def test_derived_urls_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that explicitly set derived URLs are not overwritten."""
        custom_edhlab = "https://custom.edhlab.com/create"

        monkeypatch.setenv("EDHLAB_CREATE", custom_edhlab)

        settings = Settings()

        assert custom_edhlab == settings.EDHLAB_CREATE


class TestResolvedDatabaseUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            pytest.param(
                "postgres://u@db:5432/spellbot",
                "postgresql+psycopg://u@db:5432/spellbot-test",
                id="heroku-style-scheme",
            ),
            pytest.param(
                "postgresql://u@db:5432/spellbot",
                "postgresql+psycopg://u@db:5432/spellbot-test",
                id="plain-scheme",
            ),
            pytest.param(
                "postgresql+psycopg://u@db:5432/spellbot-test",
                "postgresql+psycopg://u@db:5432/spellbot-test",
                id="already-resolved",
            ),
        ],
    )
    def test_in_pytest(self, monkeypatch: pytest.MonkeyPatch, url: str, expected: str) -> None:
        monkeypatch.setenv("DATABASE_URL", url)
        resolved = Settings().RESOLVED_DATABASE_URL
        assert resolved == expected

    def test_outside_pytest_keeps_the_database_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("spellbot.settings.running_in_pytest", lambda: False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://u@db:5432/spellbot")
        resolved = Settings().RESOLVED_DATABASE_URL
        assert resolved == "postgresql+psycopg://u@db:5432/spellbot"
