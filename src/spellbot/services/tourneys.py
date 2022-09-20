from __future__ import annotations

from typing import Any, Optional

import discord
from asgiref.sync import sync_to_async
from ddtrace import tracer

from ..database import DatabaseSession
from ..models import Tourney


class TourneysService:
    def __init__(self):
        self.tourney: Optional[Tourney] = None

    @sync_to_async
    @tracer.wrap()
    def select(self, tourney_id: int) -> bool:
        self.tourney = DatabaseSession.query(Tourney).get(tourney_id)
        return bool(self.tourney)

    @sync_to_async
    @tracer.wrap()
    def create(
        self,
        *,
        guild_xid: int,
        channel_xid: int,
        name: str,
        description: str,
        format: int,
    ) -> None:
        self.tourney = Tourney(
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            name=name,
            description=description,
            format=format,
        )
        DatabaseSession.add(self.tourney)
        DatabaseSession.commit()

    @sync_to_async
    @tracer.wrap()
    def to_embed(self) -> discord.Embed:
        assert self.tourney
        return self.tourney.to_embed()

    @sync_to_async
    @tracer.wrap()
    def to_dict(self) -> dict[str, Any]:
        assert self.tourney
        return self.tourney.to_dict()
