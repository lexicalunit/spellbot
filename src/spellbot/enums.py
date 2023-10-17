from __future__ import annotations

from collections import namedtuple
from enum import Enum
from typing import Any

# Additional metadata related to supported game formats.
FormatDetails = namedtuple("FormatDetails", ["players"])


class GameFormat(Enum):
    """A Magic: The Gathering game format."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:  # pylint: disable=W0613
        """Give each enum value an increasing numerical value starting at 1."""
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, players: int) -> None:
        """Each enum has certain additional properties taken from FormatDetails."""
        self.players = players

    def __str__(self) -> str:
        return self.name.replace("_", " ").title()

    COMMANDER = FormatDetails(players=4)
    STANDARD = FormatDetails(players=2)
    SEALED = FormatDetails(players=2)
    MODERN = FormatDetails(players=2)
    VINTAGE = FormatDetails(players=2)
    LEGACY = FormatDetails(players=2)
    BRAWL_TWO_PLAYER = FormatDetails(players=2)
    BRAWL_MULTIPLAYER = FormatDetails(players=4)
    TWO_HEADED_GIANT = FormatDetails(players=4)
    PAUPER = FormatDetails(players=2)
    PIONEER = FormatDetails(players=2)
    EDH_MAX = FormatDetails(players=4)
    EDH_HIGH = FormatDetails(players=4)
    EDH_MID = FormatDetails(players=4)
    EDH_LOW = FormatDetails(players=4)
    EDH_BATTLECRUISER = FormatDetails(players=4)
