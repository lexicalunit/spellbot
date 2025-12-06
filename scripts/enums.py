#!/usr/bin/env python
from __future__ import annotations

from spellbot.enums import GameBracket, GameFormat, GameService

print("# Brackets\n| Value | Description |\n| --- | --- |")  # noqa: T201
for bracket in GameBracket:
    print(f"| {bracket.value} | {bracket} |")  # noqa: T201

print("\n# Formats\n| Value | Description |\n| --- | --- |")  # noqa: T201
for format in GameFormat:
    print(f"| {format.value} | {format} |")  # noqa: T201

print("\n# Services\n| Value | Description |\n| --- | --- |")  # noqa: T201
for service in GameService:
    print(f"| {service.value} | {service} |")  # noqa: T201
