# Copyright (c) 2026 spellbot@lexicalunit.com

"""SQL expressions that render a game's enum columns as their display titles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import case

from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.models import Game

if TYPE_CHECKING:
    from enum import Enum

    from sqlalchemy.orm import InstrumentedAttribute
    from sqlalchemy.sql.elements import Label


def enum_label(column: InstrumentedAttribute[int], enum: type[Enum], name: str) -> Label[Any]:
    """Render `column`'s enum value as the enum member's title, or "Unknown"."""
    return case(
        *((column == member.value, str(member)) for member in enum),
        else_="Unknown",
    ).label(name)


FORMAT_LABEL = enum_label(Game.format, GameFormat, "format")
BRACKET_LABEL = enum_label(Game.bracket, GameBracket, "bracket")
SERVICE_LABEL = enum_label(Game.service, GameService, "service")
