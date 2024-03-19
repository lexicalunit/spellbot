from __future__ import annotations

from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession
from spellbot.models import Watch, WatchDict


class WatchesService:
    @sync_to_async()
    def fetch(self, guild_xid: int) -> list[WatchDict]:
        watches = (
            DatabaseSession.query(Watch)
            .filter(Watch.guild_xid == guild_xid)
            .order_by(Watch.user_xid)
            .all()
        )
        return [watch.to_dict() for watch in watches]
