#!/usr/bin/env python
from __future__ import annotations

from spellbot.enums import GameBracket, GameFormat, GameService

print("brackets:")  # noqa: T201
for bracket in GameBracket:
    print(f"{bracket.value}: {bracket}")  # noqa: T201

print("\nformats:")  # noqa: T201
for format in GameFormat:
    print(f"{format.value}: {format}")  # noqa: T201

print("\nservices:")  # noqa: T201
for service in GameService:
    print(f"{service.value}: {service}")  # noqa: T201
