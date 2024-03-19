from __future__ import annotations

import logging

from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession
from spellbot.models import Mirror, MirrorDict

logger = logging.getLogger(__name__)


class MirrorsService:
    @sync_to_async()
    def add_mirror(
        self,
        from_guild_xid: int,
        from_channel_xid: int,
        to_guild_xid: int,
        to_channel_xid: int,
    ) -> None:
        mirror = Mirror(
            from_guild_xid=from_guild_xid,
            from_channel_xid=from_channel_xid,
            to_guild_xid=to_guild_xid,
            to_channel_xid=to_channel_xid,
        )
        DatabaseSession.add(mirror)
        DatabaseSession.commit()

    @sync_to_async()
    def get(self, from_guild_xid: int, from_channel_xid: int) -> list[MirrorDict]:
        return [
            m.to_dict()
            for m in DatabaseSession.query(Mirror).filter(
                Mirror.from_guild_xid == from_guild_xid,
                Mirror.from_channel_xid == from_channel_xid,
            )
        ]
