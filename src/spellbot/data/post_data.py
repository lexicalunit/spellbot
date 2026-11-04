# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Post


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
            f"https://discord.com/channels/{self.guild_xid}/{self.channel_xid}/{self.message_xid}"
        )

    @classmethod
    def from_model(cls, model: Post) -> PostData:
        return cls(
            created_at=model.created_at,
            updated_at=model.updated_at,
            game_id=model.game_id,
            guild_xid=model.guild_xid,
            channel_xid=model.channel_xid,
            message_xid=model.message_xid,
        )
