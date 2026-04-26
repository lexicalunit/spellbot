from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueueData:
    user_xid: int
    game_id: int
    og_guild_xid: int
