"""Internationalization (i18n) support for SpellBot."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import i18n

if TYPE_CHECKING:
    import discord

# Configure i18n
TRANSLATIONS_DIR = Path(__file__).parent / "translations"
i18n.set("file_format", "yaml")
i18n.set("filename_format", "{locale}.{format}")
i18n.set("fallback", "en")
i18n.set("enable_memoization", True)
i18n.load_path.append(str(TRANSLATIONS_DIR))

# The base language codes we ship translations for (e.g. "en", "ja"). Derived
# from the translation files so adding a `<locale>.yaml` is all it takes.
AVAILABLE_LOCALES = frozenset(p.stem for p in TRANSLATIONS_DIR.glob("*.yaml"))


def t(key: str, *, locale: str = "en", **kwargs: Any) -> str:
    """Translate a key to the given locale."""
    # Normalize locale (e.g., "en-US" -> "en")
    normalized_locale = normalize_locale(locale)
    return i18n.t(key, locale=normalized_locale, **kwargs)


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
