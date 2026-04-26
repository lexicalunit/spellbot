from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerifyData:
    guild_xid: int
    user_xid: int
    verified: bool
