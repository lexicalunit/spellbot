# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Alert


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
    active_hours: dict[str, Any] | None = None
    deleted_at: datetime | None = None

    @classmethod
    def from_model(cls, model: Alert) -> AlertData:
        prefs = model.preferences or {}
        active_hours = prefs.get("active_hours")
        return cls(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            guild_xid=model.guild_xid,
            user_xid=model.user_xid,
            formats=list(prefs.get("formats") or []),
            brackets=list(prefs.get("brackets") or []),
            channels=list(prefs.get("channels") or []),
            active_hours=dict(active_hours) if active_hours else None,
            deleted_at=model.deleted_at,
        )
