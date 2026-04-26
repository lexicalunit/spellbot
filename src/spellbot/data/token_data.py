from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class TokenData:
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    key: str
    note: str | None
    scopes: str
