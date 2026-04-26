from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class GuildMemberData:
    created_at: datetime
    updated_at: datetime
    user_xid: int
    guild_xid: int
