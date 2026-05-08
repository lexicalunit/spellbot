from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class PostData:
    created_at: datetime
    updated_at: datetime
    game_id: int
    guild_xid: int
    channel_xid: int
    message_xid: int

    @property
    def jump_link(self) -> str:
        return (
            "https://discordapp.com/channels/"
            f"{self.guild_xid}/{self.channel_xid}/{self.message_xid}"
        )
