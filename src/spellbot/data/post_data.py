from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class PostData:
    created_at: datetime
    updated_at: datetime
    game_id: int
    guild_xid: int
    channel_xid: int
    message_xid: int
    jump_link: str
