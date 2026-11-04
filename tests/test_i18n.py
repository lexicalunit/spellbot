# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from babel.messages.plurals import get_plural
from babel.messages.pofile import read_po

from spellbot.i18n import (
    AVAILABLE_LOCALES,
    LANGUAGES,
    SOURCE_CATALOG,
    TRANSLATIONS_DIR,
    best_locale,
    guild_locale,
    interpolate,
    load_translation,
    message_forms,
    normalize_locale,
    parse_accept_language,
    t,
    user_locale,
)

if TYPE_CHECKING:
    from pathlib import Path

    from babel.messages.catalog import Catalog

PLACEHOLDER = re.compile(r"%\((\w+)\)s")
LINK = re.compile(r"\]\(")
BROKEN_LINK = re.compile(r"\]\s+\(")
TRANSLATED_LOCALES = sorted(AVAILABLE_LOCALES - {"en"})


def read_catalog(path: Path) -> Catalog:
    with path.open("rb") as fp:
        return read_po(fp)


def catalog_entries(path: Path) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Map each key to its (English forms, translated forms)."""
    return {
        str(message.context): (message_forms(message.id), message_forms(message.string))
        for message in read_catalog(path)
        if message.id
    }


ENGLISH = {key: english for key, (english, _) in catalog_entries(SOURCE_CATALOG).items()}


def translations(locale: str) -> dict[str, tuple[str, ...]]:
    """Each key's translated forms, leaving out untranslated entries."""
    return {
        key: translated
        for key, (_, translated) in catalog_entries(TRANSLATIONS_DIR / f"{locale}.po").items()
        if all(translated)
    }


@pytest.mark.parametrize("locale", TRANSLATED_LOCALES)
class TestTranslationFiles:
    """Catch translations that would render broken in Discord or on the web."""

    def test_in_sync_with_source(self, locale: str) -> None:
        """Every catalog has exactly the source's keys and English text; see `make translations`."""
        entries = catalog_entries(TRANSLATIONS_DIR / f"{locale}.po")
        assert {key: english for key, (english, _) in entries.items()} == ENGLISH

    def test_plural_form_count(self, locale: str) -> None:
        expected = get_plural(locale).num_plurals
        wrong = {
            key: translated
            for key, translated in translations(locale).items()
            if len(ENGLISH[key]) > 1 and len(translated) != expected
        }
        assert wrong == {}

    def test_same_placeholders_as_english(self, locale: str) -> None:
        mismatched = {
            key: translated
            for key, translated in translations(locale).items()
            for text in translated
            if set(PLACEHOLDER.findall(text)) != set(PLACEHOLDER.findall(ENGLISH[key][-1]))
        }
        assert mismatched == {}

    def test_links_are_well_formed(self, locale: str) -> None:
        broken = {
            key: translated
            for key, translated in translations(locale).items()
            for text in translated
            if BROKEN_LINK.search(text)
            or len(LINK.findall(text)) != len(LINK.findall(ENGLISH[key][-1]))
        }
        assert broken == {}

    def test_bold_markers_are_balanced(self, locale: str) -> None:
        unbalanced = {
            key: translated
            for key, translated in translations(locale).items()
            for text in translated
            if text.count("**") % 2
        }
        assert unbalanced == {}

    def test_shared_english_text_shares_one_translation(self, locale: str) -> None:
        """
        Keys with the same English text must have the same translation.

        The English string is the identity of a piece of text: `game.field.bracket` and
        `web.field.bracket` both read "Bracket" and must render the same word in every
        language. Plural entries are left out, since their forms legitimately vary.
        """
        groups: dict[str, list[str]] = {}
        for key, english in ENGLISH.items():
            if len(english) == 1:
                groups.setdefault(english[0], []).append(key)
        catalog = translations(locale)
        conflicts = {
            text: sorted({catalog[key] for key in keys if key in catalog})
            for text, keys in groups.items()
            if len({catalog[key] for key in keys if key in catalog}) > 1
        }
        assert conflicts == {}


PO_HEADER = (
    'msgid ""\n'
    'msgstr ""\n'
    '"Content-Type: text/plain; charset=utf-8\\n"\n'
    '"Plural-Forms: {plural_forms}\\n"\n\n'
)


def write_po(path: Path, body: str, *, plural_forms: str = "nplurals=2; plural=(n != 1);") -> Path:
    path.write_text(PO_HEADER.format(plural_forms=plural_forms) + body, encoding="utf-8")
    return path


class TestLoadTranslation:
    def test_skips_untranslated_and_fuzzy(self, tmp_path: Path) -> None:
        path = write_po(
            tmp_path / "xx.po",
            """msgctxt "a.done"
msgid "Done"
msgstr "Fertig"

msgctxt "a.blank"
msgid "Blank"
msgstr ""

#, fuzzy
msgctxt "a.fuzzy"
msgid "Fuzzy"
msgstr "Unsicher"

msgctxt "a.partial"
msgid "%(count)s game"
msgid_plural "%(count)s games"
msgstr[0] "%(count)s Spiel"
msgstr[1] ""
""",
        )
        language = load_translation(path)
        assert language.strings == {"a.done": ("Fertig",)}

    def test_uses_the_catalog_plural_rule(self, tmp_path: Path) -> None:
        path = write_po(tmp_path / "xx.po", "", plural_forms="nplurals=2; plural=(n > 1);")
        language = load_translation(path)
        assert [language.plural(n) for n in (0, 1, 2)] == [0, 0, 1]


class TestMessageForms:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param(None, ("",), id="none"),
            pytest.param("one", ("one",), id="string"),
            pytest.param(("one", "many"), ("one", "many"), id="tuple"),
            pytest.param(["one", "many"], ("one", "many"), id="list"),
        ],
    )
    def test_message_forms(self, value: str | list[str] | None, expected: tuple[str, ...]) -> None:
        assert message_forms(value) == expected


class TestInterpolate:
    def test_fills_placeholders(self) -> None:
        assert interpolate("%(a)s and %(b)s", {"a": 1, "b": "two"}) == "1 and two"

    def test_leaves_missing_placeholders(self) -> None:
        assert interpolate("%(a)s and %(b)s", {"a": 1}) == "1 and %(b)s"

    def test_literal_percent(self) -> None:
        assert interpolate("100%% of %(n)s", {"n": 5}) == "100% of 5"


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
        assert t("game.title.ready", locale="en") == "**Your game is ready!**"

    def test_unknown_key_returns_key(self) -> None:
        assert t("no.such.key", locale="fr") == "no.such.key"

    def test_unknown_locale_uses_english(self) -> None:
        assert t("game.title.ready", locale="xx") == "**Your game is ready!**"

    def test_untranslated_key_falls_back_to_english(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delitem(LANGUAGES["fr"].strings, "game.title.ready")
        assert t("game.title.ready", locale="fr") == "**Your game is ready!**"

    def test_english_plural(self) -> None:
        assert t("score.games", count=1) == "1 game"
        assert t("score.games", count=0) == "0 games"
        assert t("score.games", count=2) == "2 games"

    def test_plural_without_count_uses_first_form(self) -> None:
        assert t("score.games") == "%(count)s game"

    def test_count_on_a_singular_entry_is_just_a_placeholder(self) -> None:
        assert t("admin.channels_title", count=3, guild="G") == t("admin.channels_title", guild="G")

    def test_french_treats_zero_as_singular(self) -> None:
        assert t("score.games", locale="fr", count=0) == "0 partie"
        assert t("score.games", locale="fr", count=2) == "2 parties"

    def test_polish_uses_three_forms(self) -> None:
        one, few, many = (t("score.games", locale="pl", count=n) for n in (1, 3, 5))
        assert one.startswith("1 ")
        assert few.startswith("3 ")
        assert many.startswith("5 ")

    def test_japanese_has_one_form(self) -> None:
        assert t("score.games", locale="ja", count=1) == "1ゲーム"
        assert t("score.games", locale="ja", count=5) == "5ゲーム"


class TestPortugueseTranslations:
    def test_simple_string(self) -> None:
        assert t("game.title.ready", locale="pt") == "**O seu jogo está pronto!**"

    def test_string_with_named_variable(self) -> None:
        assert t("admin.channels_title", locale="pt", guild="MyGuild") == (
            "Configuração para canais em MyGuild"
        )

    def test_pluralization_singular(self) -> None:
        assert t("game.title.waiting", locale="pt", count=1) == (
            "**À espera que mais 1 jogador se junte...**"
        )

    def test_pluralization_plural(self) -> None:
        assert t("game.title.waiting", locale="pt", count=3) == (
            "**À espera que mais 3 jogadores se juntem...**"
        )

    def test_region_qualified_locale_routes_to_pt(self) -> None:
        # `t` normalizes "pt-BR" / "pt-PT" / "pt_BR" down to "pt" before lookup.
        assert t("button.join", locale="pt-BR") == "Entrar neste jogo!"
        assert t("button.join", locale="pt_PT") == "Entrar neste jogo!"

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
        # Sanity check that we're reading `pt.po`, not falling back to English.
        assert t("about.author", locale="pt") == "Autor"
        assert t("about.author", locale="en") == "Author"
