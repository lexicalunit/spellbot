from __future__ import annotations

from unittest.mock import MagicMock

from spellbot.i18n import guild_locale, normalize_locale, t, user_locale


class TestNormalizeLocale:
    def test_empty_string_returns_en(self) -> None:
        assert normalize_locale("") == "en"

    def test_valid_locale_normalized(self) -> None:
        assert normalize_locale("en-US") == "en"
        assert normalize_locale("es_MX") == "es"
        assert normalize_locale("FR") == "fr"

    def test_simple_locale(self) -> None:
        assert normalize_locale("de") == "de"


class TestGuildLocale:
    def test_none_guild_returns_en(self) -> None:
        assert guild_locale(None) == "en"

    def test_none_preferred_locale_returns_en(self) -> None:
        guild = MagicMock()
        guild.preferred_locale = None
        assert guild_locale(guild) == "en"

    def test_preferred_locale_with_value(self) -> None:
        guild = MagicMock()
        locale_enum = MagicMock()
        locale_enum.value = "es-ES"
        guild.preferred_locale = locale_enum
        assert guild_locale(guild) == "es"


class TestUserLocale:
    def test_none_locale_returns_en(self) -> None:
        interaction = MagicMock()
        interaction.locale = None
        assert user_locale(interaction) == "en"

    def test_locale_with_value(self) -> None:
        interaction = MagicMock()
        locale_enum = MagicMock()
        locale_enum.value = "fr-FR"
        interaction.locale = locale_enum
        assert user_locale(interaction) == "fr"


class TestTranslate:
    def test_t_returns_translated_string(self) -> None:
        # Test that t() function works with a known key
        result = t("game.title.ready", locale="en")
        assert isinstance(result, str)
        assert len(result) > 0
