# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from discord.app_commands import Choice

from spellbot.enums import (
    GAME_BRACKET_ORDER,
    GAME_FORMAT_ORDER,
    GAME_SERVICE_ORDER,
    MAX_SEATS,
    MIN_SEATS,
)

SEAT_CHOICES = [Choice(name=str(seats), value=seats) for seats in range(MIN_SEATS, MAX_SEATS + 1)]
FORMAT_CHOICES = [Choice(name=str(format), value=format.value) for format in GAME_FORMAT_ORDER]
BRACKET_CHOICES = [Choice(name=str(bracket), value=bracket.value) for bracket in GAME_BRACKET_ORDER]
SERVICE_CHOICES = [Choice(name=str(service), value=service.value) for service in GAME_SERVICE_ORDER]
