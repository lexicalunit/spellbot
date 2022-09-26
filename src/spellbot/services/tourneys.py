from __future__ import annotations

from typing import Any, Optional

import discord
from asgiref.sync import sync_to_async
from ddtrace import tracer

from spellbot.models.game import GameFormat

from ..database import DatabaseSession
from ..models import Tourney


class TourneysService:
    def __init__(self):
        self.tourney: Optional[Tourney] = None

    @sync_to_async
    @tracer.wrap()
    def create(
        self,
        *,
        guild_xid: int,
        channel_xid: int,
        name: str,
        description: str,
    ) -> dict[str, Any]:
        self.tourney = Tourney(
            guild_xid=guild_xid,
            channel_xid=channel_xid,
            name=name,
            description=description,
            format=GameFormat.COMMANDER,
        )
        DatabaseSession.add(self.tourney)
        DatabaseSession.commit()
        return self.tourney.to_dict()

    @sync_to_async
    @tracer.wrap()
    def select(self, tourney_id: int) -> Optional[dict[str, Any]]:
        self.tourney = DatabaseSession.query(Tourney).filter(Tourney.id == tourney_id).one_or_none()
        return self.tourney.to_dict() if self.tourney else None

    @sync_to_async
    @tracer.wrap()
    def select_by_message_xid(self, message_xid: int) -> Optional[dict[str, Any]]:
        self.tourney = (
            DatabaseSession.query(Tourney).filter(Tourney.message_xid == message_xid).one_or_none()
        )
        return self.tourney.to_dict() if self.tourney else None

    @sync_to_async
    @tracer.wrap()
    def set_message_xid(self, message_xid: int) -> dict[str, Any]:
        assert self.tourney
        self.tourney.message_xid = message_xid  # type: ignore
        DatabaseSession.commit()
        return self.tourney.to_dict()

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
