# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import User


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
    is_admin: bool = False
    playgroup_user_id: int | None = None
    locale: str = "en"

    @classmethod
    def from_model(cls, model: User) -> UserData:
        return cls(
            xid=model.xid,
            created_at=model.created_at,
            updated_at=model.updated_at,
            name=model.name,
            banned=model.banned,
            is_admin=model.is_admin,
            playgroup_user_id=model.playgroup_user_id,
            locale=model.locale,
        )
