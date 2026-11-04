# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from spellbot.enums import GameBracket, GameFormat, GameService

if TYPE_CHECKING:
    from datetime import datetime

    from spellbot.models import Channel


@dataclass
class ChannelData:
    xid: int
    created_at: datetime
    updated_at: datetime
    guild_xid: int
    name: str | None
    default_seats: int
    default_format: GameFormat
    default_bracket: GameBracket
    default_service: GameService
    motd: str | None
    extra: str | None
    voice_category: str | None
    voice_invite: bool
    delete_expired: bool
    blind_games: bool
    to_mode: bool
    competitive_mode: bool

    @classmethod
    def from_model(cls, model: Channel) -> ChannelData:
        return cls(
            xid=model.xid,
            created_at=model.created_at,
            updated_at=model.updated_at,
            guild_xid=model.guild_xid,
            name=model.name,
            default_seats=model.default_seats,
            default_format=GameFormat(model.default_format),
            default_bracket=GameBracket(model.default_bracket),
            default_service=GameService(model.default_service),
            motd=model.motd,
            extra=model.extra,
            voice_category=model.voice_category,
            voice_invite=model.voice_invite,
            delete_expired=model.delete_expired,
            blind_games=model.blind_games,
            to_mode=model.to_mode,
            competitive_mode=model.competitive_mode,
        )
