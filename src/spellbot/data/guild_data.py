from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.data.award_data import GuildAwardData
    from spellbot.data.channel_data import ChannelData


@dataclass
class GuildData:
    xid: int
    created_at: datetime
    updated_at: datetime
    name: str | None
    motd: str | None
    show_links: bool
    voice_create: bool
    use_max_bitrate: bool
    banned: bool
    notice: str | None
    suggest_voice_category: str | None
    enable_mythic_track: bool
    channels: list[ChannelData] = field(default_factory=list)
    awards: list[GuildAwardData] = field(default_factory=list)
