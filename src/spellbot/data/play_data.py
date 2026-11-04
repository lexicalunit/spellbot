# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Play


@dataclass
class PlayData:
    created_at: datetime
    updated_at: datetime
    user_xid: int
    game_id: int
    og_guild_xid: int
    pin: str | None
    verified_at: datetime | None

    @classmethod
    def from_model(cls, model: Play) -> PlayData:
        return cls(
            created_at=model.created_at,
            updated_at=model.updated_at,
            user_xid=model.user_xid,
            game_id=model.game_id,
            og_guild_xid=model.og_guild_xid,
            pin=model.pin,
            verified_at=model.verified_at,
        )
