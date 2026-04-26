from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.enums import GameBracket, GameFormat, GameService


@dataclass
class ChannelData:
    xid: int
    created_at: datetime
    updated_at: datetime
    guild_xid: int
    name: str | None
    default_seats: int
    default_format: GameFormat
    default_bracket: GameBracket
    default_service: GameService
    auto_verify: bool
    unverified_only: bool
    verified_only: bool
    motd: str | None
    extra: str | None
    voice_category: str | None
    voice_invite: bool
    delete_expired: bool
    blind_games: bool
