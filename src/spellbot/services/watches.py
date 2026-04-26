from __future__ import annotations

from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession
from spellbot.models import Watch

if TYPE_CHECKING:
    from spellbot.data import WatchData


class WatchesService:
    @sync_to_async()
    def fetch(self, guild_xid: int) -> list[WatchData]:
        """Fetch all watches for the given guild."""
        watches = (
            DatabaseSession.query(Watch)
            .filter(Watch.guild_xid == guild_xid)
            .order_by(Watch.user_xid)
            .all()
        )
        return [watch.to_data() for watch in watches]
