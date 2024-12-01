from __future__ import annotations

from enum import Enum
from typing import Any, NamedTuple


# Additional metadata related to supported game formats.
class FormatDetails(NamedTuple):
    players: int


class GameService(Enum):
    """A service for playing Magic: The Gathering games."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """Give each enum value an increasing numerical value starting at 1."""
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, title: str) -> None:
        self.title = title

    def __str__(self) -> str:
        return self.title

    # DO NOT REORDER -- IT WOULD INVALIDATE EXISTING DATABASE ENTRIES!
    NOT_ANY = "Not any"
    SPELLTABLE = "SpellTable"
    COCKATRICE = "Cockatrice"
    X_MAGE = "XMage"
    MTG_ARENA = "MTG Arena"
    MTG_ONLINE = "MTG Online"
    TTS = "TabletopSim"
    TABLE_STREAM = "Table Stream"


GAME_SERVICE_ORDER = [
    GameService.NOT_ANY,
    GameService.SPELLTABLE,
    GameService.TABLE_STREAM,
    GameService.COCKATRICE,
    GameService.X_MAGE,
    GameService.MTG_ARENA,
    GameService.MTG_ONLINE,
    GameService.TTS,
]


class GameFormat(Enum):
    """A Magic: The Gathering game format."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
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
