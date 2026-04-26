from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WatchData:
    guild_xid: int
    user_xid: int
    note: str | None
