# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Block


@dataclass
class BlockData:
    created_at: datetime
    updated_at: datetime
    user_xid: int
    blocked_user_xid: int

    @classmethod
    def from_model(cls, model: Block) -> BlockData:
        return cls(
            created_at=model.created_at,
            updated_at=model.updated_at,
            user_xid=model.user_xid,
            blocked_user_xid=model.blocked_user_xid,
        )
