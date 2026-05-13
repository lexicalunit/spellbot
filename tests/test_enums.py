from __future__ import annotations

import importlib
from unittest.mock import patch

import spellbot.enums as enums_module
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
    expected = {s for s in GameService if s is not GameService.PLAYGROUP_LIVE}
    assert expected.issubset(set(GAME_SERVICE_ORDER))
    assert len(GAME_SERVICE_ORDER) == len(set(GAME_SERVICE_ORDER))


def test_game_bracket_ordering() -> None:
    assert all(f in GAME_BRACKET_ORDER for f in GameBracket)
    assert len(GAME_BRACKET_ORDER) == len(set(GAME_BRACKET_ORDER))


def test_GAME_SERVICE_ORDER_with_playgroup_api_key() -> None:
    with patch.object(enums_module.settings, "PLAYGROUP_LIVE_API_KEY", "test-key"):
        reloaded = importlib.reload(enums_module)
        try:
            assert reloaded.GameService.PLAYGROUP_LIVE in reloaded.GAME_SERVICE_ORDER
        finally:
            importlib.reload(enums_module)


def test_GAME_SERVICE_ORDER_without_playgroup_api_key() -> None:
    with patch.object(enums_module.settings, "PLAYGROUP_LIVE_API_KEY", ""):
        reloaded = importlib.reload(enums_module)
        try:
            assert reloaded.GameService.PLAYGROUP_LIVE not in reloaded.GAME_SERVICE_ORDER
        finally:
            importlib.reload(enums_module)
