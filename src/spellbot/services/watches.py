from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession
from spellbot.models.watch import Watch
from spellbot.services import BaseService


class WatchesService(BaseService):
    @sync_to_async
    def fetch(self, guild_xid: int) -> list[dict]:
        watches = (
            DatabaseSession.query(Watch)
            .filter(Watch.guild_xid == guild_xid)
            .order_by(Watch.user_xid)
            .all()
        )
        return [watch.to_dict() for watch in watches]
