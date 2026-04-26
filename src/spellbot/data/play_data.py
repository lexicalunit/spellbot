from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class PlayData:
    created_at: datetime
    updated_at: datetime
    user_xid: int
    game_id: int
    og_guild_xid: int
    pin: str | None
    verified_at: datetime | None
