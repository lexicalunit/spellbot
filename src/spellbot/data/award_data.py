from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GuildAwardData:
    id: int
    guild_xid: int
    count: int
    repeating: bool
    remove: bool
    role: str
    message: str
    verified_only: bool
    unverified_only: bool


@dataclass
class UserAwardData:
    user_xid: int
    guild_xid: int
    guild_award_id: int | None
