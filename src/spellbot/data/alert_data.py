from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class AlertData:
    id: int
    created_at: datetime
    updated_at: datetime
    guild_xid: int
    user_xid: int
    formats: list[int] = field(default_factory=list)
    brackets: list[int] = field(default_factory=list)
    channels: list[int] = field(default_factory=list)
