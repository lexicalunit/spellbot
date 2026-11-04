# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import gettext
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from babel.messages.plurals import get_plural
from babel.messages.pofile import read_po

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    import discord

# The English source strings live in `messages.pot`, one entry per key: the key is the
# entry's `msgctxt` and the English text its `msgid`. Each `<lang>.po` holds that
# language's translations of the same entries. See `CONTRIBUTING.md` for editing them.
TRANSLATIONS_DIR = Path(__file__).parent / "translations"
SOURCE_CATALOG = TRANSLATIONS_DIR / "messages.pot"

# `%(name)s` placeholders, plus `%%` for a literal percent sign.
PLACEHOLDER = re.compile(r"%(?:\((\w+)\)s|%)")


@dataclass(frozen=True)
class Language:
    """One language's strings by key, each a tuple of its plural forms (just one if none)."""

    plural: Callable[[int], int]
    strings: dict[str, tuple[str, ...]]

    def forms(self, key: str) -> tuple[str, ...] | None:
        return self.strings.get(key)


def message_forms(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Return a catalog message's text as a tuple of its plural forms (one if no plural)."""
    if value is None:
        return ("",)
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def load_source() -> Language:
    with SOURCE_CATALOG.open("rb") as fp:
        catalog = read_po(fp)
    strings = {
        str(message.context): message_forms(message.id)
        for message in catalog
        if message.id and message.context
    }
    return Language(plural=gettext.c2py(get_plural("en").plural_expr), strings=strings)


def load_translation(path: Path) -> Language:
    """Load a `<lang>.po`, skipping untranslated and fuzzy entries so they fall back to English."""
    with path.open("rb") as fp:
        catalog = read_po(fp)
    strings: dict[str, tuple[str, ...]] = {}
    for message in catalog:
        if not message.id or not message.context or message.fuzzy:
            continue
        forms = message_forms(message.string)
        if all(forms):
            strings[str(message.context)] = forms
    return Language(plural=gettext.c2py(catalog.plural_expr), strings=strings)


ENGLISH = load_source()
LANGUAGES: dict[str, Language] = {
    "en": ENGLISH,
    **{path.stem: load_translation(path) for path in sorted(TRANSLATIONS_DIR.glob("*.po"))},
}

# The base language codes we ship translations for (e.g. "en", "ja"). Derived
# from the translation files so adding a `<lang>.po` is all it takes.
AVAILABLE_LOCALES = frozenset(LANGUAGES)


def interpolate(text: str, values: dict[str, Any]) -> str:
    """Fill `%(name)s` placeholders, leaving any without a value as they are."""

    def fill(match: re.Match[str]) -> str:
        name = match[1]
        if name is None:
            return "%"
        return str(values[name]) if name in values else match[0]

    return PLACEHOLDER.sub(fill, text)


def t(key: str, *, locale: str = "en", **kwargs: Any) -> str:
    """
    Translate `key` into `locale`, falling back to English and then to the key itself.

    Keyword arguments fill the string's placeholders. A `count` also picks the plural
    form, using the language's own plural rule.
    """
    language = LANGUAGES.get(normalize_locale(locale), ENGLISH)
    forms = language.forms(key)
    if forms is None:
        language, forms = ENGLISH, ENGLISH.forms(key)
    if forms is None:
        return key
    text = forms[0]
    if len(forms) > 1 and isinstance(count := kwargs.get("count"), int):
        text = forms[min(language.plural(count), len(forms) - 1)]
    return interpolate(text, kwargs)


def normalize_locale(locale: str) -> str:
    """Normalize a locale string to a base language code."""
    if not locale:
        return "en"
    # Handle both "en-US" and "en_US" formats using regex
    match = re.match(r"^([a-zA-Z]+)", locale)
    return match.group(1).lower() if match else "en"


def parse_accept_language(header: str) -> list[str]:
    """Return language tags from an `Accept-Language` header, best-quality first."""
    tagged: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        bits = part.strip().split(";")
        tag = bits[0].strip()
        if not tag or tag == "*":
            continue
        quality = 1.0
        for raw_param in bits[1:]:
            param = raw_param.strip()
            if param.startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
        # Sort by quality descending, then original order ascending for ties.
        tagged.append((-quality, index, tag))
    return [tag for _, _, tag in sorted(tagged)]


def best_locale(accept_language: str | None) -> str:
    """Pick the best available locale from an `Accept-Language` header."""
    if not accept_language:
        return "en"
    for tag in parse_accept_language(accept_language):
        code = normalize_locale(tag)
        if code in AVAILABLE_LOCALES:
            return code
    return "en"


def guild_locale(guild: discord.Guild | None) -> str:
    """Get the locale for a guild."""
    if guild is None:
        return "en"
    preferred = guild.preferred_locale
    if preferred is None:
        return "en"
    # preferred_locale is a discord.Locale enum, get its value
    return normalize_locale(str(preferred.value) if hasattr(preferred, "value") else str(preferred))


def user_locale(interaction: discord.Interaction) -> str:
    """Get the locale for a user from an interaction."""
    locale = interaction.locale
    if locale is None:
        return "en"
    return normalize_locale(str(locale.value) if hasattr(locale, "value") else str(locale))
