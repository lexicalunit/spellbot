# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Guild


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
    active: bool = True
    locale: str = "en"
    icon: str | None = None
    promote: bool = True
    show_convoke_guild: bool = True

    @classmethod
    def from_model(cls, model: Guild) -> GuildData:
        return cls(
            xid=model.xid,
            created_at=model.created_at,
            updated_at=model.updated_at,
            name=model.name,
            motd=model.motd,
            show_links=model.show_links,
            voice_create=model.voice_create,
            use_max_bitrate=model.use_max_bitrate,
            banned=model.banned,
            notice=model.notice,
            suggest_voice_category=model.suggest_voice_category,
            enable_mythic_track=model.enable_mythic_track,
            show_convoke_guild=model.show_convoke_guild,
            active=model.active,
            locale=model.locale,
            icon=model.icon,
            promote=model.promote,
        )
