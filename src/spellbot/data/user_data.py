from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from datetime import datetime


class PlayerDataDict(TypedDict):
    xid: int
    name: str


@dataclass
class UserData:
    xid: int
    created_at: datetime
    updated_at: datetime
    name: str
    banned: bool
