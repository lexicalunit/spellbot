from __future__ import annotations

from spellbot.enums import GAME_FORMAT_ORDER, GameFormat


def test_game_format_ordering() -> None:
    assert all(f in GAME_FORMAT_ORDER for f in GameFormat)
    assert len(GAME_FORMAT_ORDER) == len(set(GAME_FORMAT_ORDER))
