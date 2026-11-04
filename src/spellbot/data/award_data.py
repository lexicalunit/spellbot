# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spellbot.models import GuildAward, UserAward


@dataclass
class GuildAwardData:
    id: int
    guild_xid: int
    count: int
    repeating: bool
    remove: bool
    role: str
    message: str

    @classmethod
    def from_model(cls, model: GuildAward) -> GuildAwardData:
        return cls(
            id=model.id,
            guild_xid=model.guild_xid,
            count=model.count,
            repeating=model.repeating,
            remove=model.remove,
            role=model.role,
            message=model.message,
        )


@dataclass
class UserAwardData:
    user_xid: int
    guild_xid: int
    guild_award_id: int | None

    @classmethod
    def from_model(cls, model: UserAward) -> UserAwardData:
        return cls(
            user_xid=model.user_xid,
            guild_xid=model.guild_xid,
            guild_award_id=model.guild_award_id,
        )
