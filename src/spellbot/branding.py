from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class Theme(StrEnum):
    DEFAULT = "default"
    PRIDE = "pride"
    BLACK_HISTORY = "black"
    TRANS = "trans"
    AUTISM = "autism"
    CONVOKE = "convoke"


@dataclass(frozen=True)
class ThemeConfig:
    theme: Theme
    thumb_url: str


THEME_ASSET_BASE = "https://spellbot.io/assets/img"

THEME_CONFIGS: dict[Theme, ThemeConfig] = {
    Theme.DEFAULT: ThemeConfig(
        Theme.DEFAULT,
        "https://raw.githubusercontent.com/lexicalunit/spellbot/main/spellbot.png",
    ),
    Theme.PRIDE: ThemeConfig(Theme.PRIDE, f"{THEME_ASSET_BASE}/logos/spellbot-lgbtq.png"),
    Theme.BLACK_HISTORY: ThemeConfig(
        Theme.BLACK_HISTORY, f"{THEME_ASSET_BASE}/logos/spellbot-black.png"
    ),
    Theme.TRANS: ThemeConfig(Theme.TRANS, f"{THEME_ASSET_BASE}/logos/spellbot-trans.png"),
    Theme.AUTISM: ThemeConfig(Theme.AUTISM, f"{THEME_ASSET_BASE}/logos/spellbot-autistic.png"),
    Theme.CONVOKE: ThemeConfig(Theme.CONVOKE, f"{THEME_ASSET_BASE}/servers/convoke.png"),
}

GUILD_THEME_OVERRIDES: dict[int, Theme] = {
    1417960690110697504: Theme.CONVOKE,  # Convoke
}

PRIDE_GUILDS: frozenset[int] = frozenset(
    {
        757455940009328670,  # Oath of the Gaywatch
        699775410082414733,  # Development
    }
)


def is_pride(guild_xid: int | None, now: datetime) -> bool:
    """Pride Month (June) or year-round for specific guilds."""
    return now.month == 6 or (guild_xid is not None and guild_xid in PRIDE_GUILDS)


def is_black_history(guild_xid: int | None, now: datetime) -> bool:
    """Black History Month (February)."""
    return now.month == 2


def is_trans(guild_xid: int | None, now: datetime) -> bool:
    """Trans Awareness Month (November) or Trans Day of Visibility (March 31)."""
    return now.month == 11 or (now.month == 3 and now.day == 31)


def is_autism_awareness(guild_xid: int | None, now: datetime) -> bool:
    """World Autism Awareness Day (April 2)."""
    return now.month == 4 and now.day == 2


@dataclass(frozen=True)
class ThemeRule:
    theme: Theme
    matcher: Callable[[int | None, datetime], bool]


# Priority order matters - first match wins
THEME_RULES: tuple[ThemeRule, ...] = (
    ThemeRule(Theme.AUTISM, is_autism_awareness),
    ThemeRule(Theme.TRANS, is_trans),
    ThemeRule(Theme.PRIDE, is_pride),
    ThemeRule(Theme.BLACK_HISTORY, is_black_history),
)


def get_theme(guild_xid: int | None, now: datetime | None = None) -> Theme:
    """
    Determine the active theme for a guild at a given time.

    Priority:
    1. Guild-specific overrides (e.g., Convoke)
    2. Date-based themes in order: Autism > Trans > Pride > Black History
    3. Default theme
    """
    if now is None:
        now = datetime.now(tz=UTC)

    if guild_xid is not None and guild_xid in GUILD_THEME_OVERRIDES:
        return GUILD_THEME_OVERRIDES[guild_xid]

    for rule in THEME_RULES:
        if rule.matcher(guild_xid, now):
            return rule.theme

    return Theme.DEFAULT


def get_thumb_url(guild_xid: int | None, now: datetime | None = None) -> str:
    """
    Get the thumbnail URL for a guild at a given time.

    This is the main entry point for getting the branding image URL.
    """
    theme = get_theme(guild_xid, now)
    return THEME_CONFIGS[theme].thumb_url
