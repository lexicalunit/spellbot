from __future__ import annotations

from spellbot.enums import (
    GAME_BRACKET_ORDER,
    GAME_FORMAT_ORDER,
    GAME_SERVICE_ORDER,
    GameBracket,
    GameFormat,
    GameService,
)


def test_game_format_ordering() -> None:
    assert all(f in GAME_FORMAT_ORDER for f in GameFormat)
    assert len(GAME_FORMAT_ORDER) == len(set(GAME_FORMAT_ORDER))


def test_game_service_ordering() -> None:
    assert all(f in GAME_SERVICE_ORDER for f in GameService)
    assert len(GAME_SERVICE_ORDER) == len(set(GAME_SERVICE_ORDER))


def test_game_bracket_ordering() -> None:
    assert all(f in GAME_BRACKET_ORDER for f in GameBracket)
    assert len(GAME_BRACKET_ORDER) == len(set(GAME_BRACKET_ORDER))
