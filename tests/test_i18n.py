from __future__ import annotations

from unittest.mock import MagicMock

from spellbot.i18n import (
    best_locale,
    guild_locale,
    normalize_locale,
    parse_accept_language,
    t,
    user_locale,
)


class TestParseAcceptLanguage:
    def test_quality_ordering(self) -> None:
        assert parse_accept_language("de;q=0.7,fr;q=0.9,en;q=0.8") == ["fr", "en", "de"]

    def test_default_quality_and_order(self) -> None:
        assert parse_accept_language("en-US,en;q=0.9,fr;q=0.8") == ["en-US", "en", "fr"]

    def test_ignores_wildcard_and_blanks(self) -> None:
        assert parse_accept_language("*, , ja") == ["ja"]

    def test_ignores_non_quality_parameters(self) -> None:
        # A non-`q=` parameter is skipped; quality defaults to 1.0.
        assert parse_accept_language("en;foo=bar") == ["en"]

    def test_malformed_quality_sorts_last(self) -> None:
        # An unparseable q-value is treated as 0.0, so `fr` outranks `en`.
        assert parse_accept_language("en;q=abc,fr;q=0.5") == ["fr", "en"]


class TestBestLocale:
    def test_none_returns_en(self) -> None:
        assert best_locale(None) == "en"

    def test_empty_returns_en(self) -> None:
        assert best_locale("") == "en"

    def test_picks_first_available(self) -> None:
        assert best_locale("en-US,en;q=0.9,fr;q=0.8") == "en"
        assert best_locale("fr-CA,fr;q=0.9") == "fr"
        assert best_locale("ja,en;q=0.5") == "ja"

    def test_quality_wins_over_order(self) -> None:
        assert best_locale("de;q=0.7,fr;q=0.9") == "fr"

    def test_skips_unavailable_locales(self) -> None:
        # zh and ko are not shipped; falls through to the available fr.
        assert best_locale("zh-CN,ko;q=0.9,fr;q=0.5") == "fr"

    def test_no_available_falls_back_to_en(self) -> None:
        assert best_locale("zh-CN,ko;q=0.8") == "en"


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


class TestPortugueseTranslations:
    def test_simple_string(self) -> None:
        assert t("game.title.ready", locale="pt") == "**O seu jogo está pronto!**"

    def test_string_with_named_variable(self) -> None:
        assert t("admin.channels_title", locale="pt", guild="MyGuild") == (
            "Configuração para canais em MyGuild"
        )

    def test_pluralization_singular(self) -> None:
        assert t("game.title.waiting_one", locale="pt", count=1) == (
            "**À espera que mais 1 jogador se junte...**"
        )

    def test_pluralization_plural(self) -> None:
        assert t("game.title.waiting_many", locale="pt", count=3) == (
            "**À espera que mais 3 jogadores se juntem...**"
        )

    def test_region_qualified_locale_routes_to_pt(self) -> None:
        # `t` normalizes "pt-BR" / "pt-PT" / "pt_BR" down to "pt" before lookup.
        assert t("watch.title", locale="pt-BR") == "Utilizadores observados juntaram-se a um jogo"
        assert t("watch.title", locale="pt_PT") == "Utilizadores observados juntaram-se a um jogo"

    def test_user_locale_pt_returns_pt_translation(self) -> None:
        interaction = MagicMock()
        locale_enum = MagicMock()
        locale_enum.value = "pt-BR"
        interaction.locale = locale_enum
        locale = user_locale(interaction)
        assert locale == "pt"
        assert t("button.join", locale=locale) == "Entrar neste jogo!"

    def test_guild_locale_pt_returns_pt_translation(self) -> None:
        guild = MagicMock()
        locale_enum = MagicMock()
        locale_enum.value = "pt-BR"
        guild.preferred_locale = locale_enum
        locale = guild_locale(guild)
        assert locale == "pt"
        assert t("admin.done", locale=locale) == "Concluído."

    def test_pt_differs_from_en_for_translated_keys(self) -> None:
        # Sanity check that we're actually reading from `pt.yaml`, not falling
        # back to `en.yaml`, for a key that has been translated.
        assert t("about.author", locale="pt") == "Autor"
        assert t("about.author", locale="en") == "Author"
