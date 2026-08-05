from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class WebActionData:
    id: int
    created_at: datetime
    updated_at: datetime
    user_xid: int
    guild_xid: int
    channel_xid: int
    kind: str
    status: str
    locale: str
    resolved_at: datetime | None = None
    game_id: int | None = None
    error_code: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    notices: list[str] = field(default_factory=list)
