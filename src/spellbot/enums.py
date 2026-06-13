from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from spellbot.i18n import t
from spellbot.settings import settings

if TYPE_CHECKING:
    import discord


class GameService(Enum):
    """A service for playing Magic: The Gathering games."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG004
        """Give each enum value an increasing numerical value starting at 1."""
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(
        self,
        title: str,
        translation_key: str,
        fallback_url: str | None,
        max_seats: int,
    ) -> None:
        """Build a service for Magic: The Gathering games."""
        self.title = title
        self.translation_key = translation_key
        self.fallback_url = fallback_url
        self.max_seats = max_seats

    def __str__(self) -> str:
        return self.title

    def get_pending_msg(
        self,
        locale: str = "en",
        emojis: list[discord.Emoji] | list[discord.PartialEmoji | discord.Emoji] | None = None,
    ) -> str:
        """Get the pending message for this service, with optional emoji."""
        emoji_str = ""
        if emojis:
            emoji_name = self.name.lower().replace("-", "_").replace(" ", "_")
            if emoji := next((e for e in emojis if e.name == emoji_name), None):
                emoji_str = f"{emoji} "
        return t(f"service.{self.translation_key}", locale=locale, emoji=emoji_str)

    # DO NOT REORDER -- IT WOULD INVALIDATE EXISTING DATABASE ENTRIES!
    NOT_ANY = "Not any", "not_any", None, 8
    SPELLTABLE = "SpellTable", "spelltable", None, 4
    COCKATRICE = "Cockatrice", "cockatrice", None, 5
    X_MAGE = "XMage", "xmage", None, 10
    MTG_ARENA = "MTG Arena", "mtg_arena", None, 2
    MTG_ONLINE = "MTG Online", "mtg_online", None, 4
    TTS = "TabletopSim", "tts", None, 10
    TABLE_STREAM = "Table Stream", "table_stream", "https://table-stream.com/", 6
    CONVOKE = "Convoke", "convoke", "https://www.convoke.games/", 8
    GIRUDO = "Girudo", "girudo", "https://www.girudo.com/", 4
    EDHLAB = "EDHLAB", "edhlab", "https://edhlab.gg/", 4
    PLAYGROUP_LIVE = "Playgroup Live", "playgroup_live", "https://playgroup.gg/", 6


GAME_SERVICE_ORDER = [
    GameService.CONVOKE,
    *([GameService.PLAYGROUP_LIVE] if settings.PLAYGROUP_LIVE_API_KEY else []),
    GameService.TABLE_STREAM,
    GameService.GIRUDO,
    GameService.EDHLAB,
    GameService.SPELLTABLE,
    GameService.COCKATRICE,
    GameService.X_MAGE,
    GameService.MTG_ARENA,
    GameService.MTG_ONLINE,
    GameService.TTS,
    GameService.NOT_ANY,
]


class GameFormat(Enum):
    """A Magic: The Gathering game format."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG004
        """Give each enum value an increasing numerical value starting at 1."""
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, players: int, title: str | None = None) -> None:
        """Build a format with its default player count and an optional display title."""
        self.players = players
        self.title = title

    def __str__(self) -> str:
        return self.title if self.title is not None else self.name.replace("_", " ").title()

    # DO NOT REORDER -- IT WOULD INVALIDATE EXISTING DATABASE ENTRIES!
    COMMANDER = 4
    STANDARD = 2
    SEALED = 2
    MODERN = 2
    VINTAGE = 2
    LEGACY = 2
    BRAWL_TWO_PLAYER = 2, "Brawl (Two Players)"
    BRAWL_MULTIPLAYER = 4, "Brawl (Multiplayer)"
    TWO_HEADED_GIANT = 4
    PAUPER = 2
    PIONEER = 2
    EDH_MAX = 4, "EDH Max"
    EDH_HIGH = 4, "EDH High"
    EDH_MID = 4, "EDH Mid"
    EDH_LOW = 4, "EDH Low"
    EDH_BATTLECRUISER = 4, "EDH Battlecruiser"
    PLANECHASE = 4
    PRE_CONS = 4, "Commander Precons"
    OATHBREAKER = 4
    DUEL_COMMANDER = 2
    CEDH = 4, "cEDH"
    ARCHENEMY = 4
    PAUPER_EDH = 4, "Pauper EDH"
    HORDE_MAGIC = 4, "Horde Magic"


GAME_FORMAT_ORDER = [
    GameFormat.COMMANDER,
    GameFormat.PRE_CONS,
    GameFormat.EDH_LOW,
    GameFormat.EDH_MID,
    GameFormat.EDH_HIGH,
    GameFormat.EDH_MAX,
    GameFormat.EDH_BATTLECRUISER,
    GameFormat.PLANECHASE,
    GameFormat.TWO_HEADED_GIANT,
    GameFormat.BRAWL_MULTIPLAYER,
    GameFormat.CEDH,
    GameFormat.PAUPER_EDH,
    GameFormat.OATHBREAKER,
    GameFormat.ARCHENEMY,
    GameFormat.HORDE_MAGIC,
    GameFormat.DUEL_COMMANDER,
    GameFormat.STANDARD,
    GameFormat.MODERN,
    GameFormat.PIONEER,
    GameFormat.PAUPER,
    GameFormat.LEGACY,
    GameFormat.VINTAGE,
    GameFormat.SEALED,
    GameFormat.BRAWL_TWO_PLAYER,
]


class GameBracket(Enum):
    """The bracket for this game."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG004
        """Give each enum value an increasing numerical value starting at 1."""
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, title: str, icon: str | None) -> None:
        self.title = title
        self.icon = icon

    def __str__(self) -> str:
        return self.title

    # DO NOT REORDER -- IT WOULD INVALIDATE EXISTING DATABASE ENTRIES!
    NONE = "None", None
    BRACKET_1 = "Bracket 1: Exhibition", "✧"
    BRACKET_2 = "Bracket 2: Core", "✦"
    BRACKET_3 = "Bracket 3: Upgraded", "★"
    BRACKET_4 = "Bracket 4: Optimized", "✷"
    BRACKET_5 = "Bracket 5: Competitive", "✺"


GAME_BRACKET_ORDER = [
    GameBracket.NONE,
    GameBracket.BRACKET_1,
    GameBracket.BRACKET_2,
    GameBracket.BRACKET_3,
    GameBracket.BRACKET_4,
    GameBracket.BRACKET_5,
]

MIN_SEATS = min(service.max_seats for service in GameService)
MAX_SEATS = max(service.max_seats for service in GameService)

VALID_FORMATS = frozenset(game_format.value for game_format in GameFormat)
VALID_BRACKETS = frozenset(game_bracket.value for game_bracket in GameBracket)
VALID_SERVICES = frozenset(game_service.value for game_service in GameService)
