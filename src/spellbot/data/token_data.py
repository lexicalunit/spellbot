# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Token


@dataclass
class TokenData:
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    key_hash: str
    note: str | None
    scopes: str

    @classmethod
    def from_model(cls, model: Token) -> TokenData:
        return cls(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            key_hash=model.key_hash,
            note=model.note,
            scopes=model.scopes,
        )
