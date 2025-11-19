from __future__ import annotations

from enum import Enum
from typing import Any, NamedTuple


# Additional metadata related to supported game formats.
class FormatDetails(NamedTuple):
    players: int


class GameService(Enum):
    """A service for playing Magic: The Gathering games."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG004
        """Give each enum value an increasing numerical value starting at 1."""
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, title: str, pending_msg: str, fallback_url: str | None) -> None:
        """
        Build a service for Magic: The Gathering games.

        - title: The human readable name of the service.
        - pending_msg: A message to display when a game is pending for this service.
        - fallback_url: A fallback URL where users can manually create a game if needed.
        """
        self.title = title
        self.pending_msg = pending_msg
        self.fallback_url = fallback_url

    def __str__(self) -> str:
        return self.title

    # DO NOT REORDER -- IT WOULD INVALIDATE EXISTING DATABASE ENTRIES!
    NOT_ANY = "Not any", "_Please contact the players in your game to organize this game._", None
    SPELLTABLE = (
        "SpellTable",
        "_A SpellTable link will be created when all players have joined._",
        "https://spelltable.wizards.com/",
    )
    COCKATRICE = "Cockatrice", "_Please use Cockatrice for this game._", None
    X_MAGE = "XMage", "_Please use XMage for this game._", None
    MTG_ARENA = "MTG Arena", "_Please use MTG Arena for this game._", None
    MTG_ONLINE = "MTG Online", "_Please use MTG Online for this game._", None
    TTS = "TabletopSim", "_Please use TabletopSim for this game._", None
    TABLE_STREAM = (
        "Table Stream",
        "_A Table Stream link will be created when all players have joined._",
        "https://table-stream.com/",
    )
    CONVOKE = "Convoke", "_Please use Convoke for this game._", "https://www.convoke.games/"


GAME_SERVICE_ORDER = [
    GameService.NOT_ANY,
    GameService.SPELLTABLE,
    GameService.CONVOKE,
    GameService.TABLE_STREAM,
    GameService.COCKATRICE,
    GameService.X_MAGE,
    GameService.MTG_ARENA,
    GameService.MTG_ONLINE,
    GameService.TTS,
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
        """Each enum has certain additional properties taken from FormatDetails."""
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
