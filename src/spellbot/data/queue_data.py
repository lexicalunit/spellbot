# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spellbot.models import Queue


@dataclass
class QueueData:
    user_xid: int
    game_id: int
    og_guild_xid: int

    @classmethod
    def from_model(cls, model: Queue) -> QueueData:
        return cls(
            user_xid=model.user_xid,
            game_id=model.game_id,
            og_guild_xid=model.og_guild_xid,
        )
