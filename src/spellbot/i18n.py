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
