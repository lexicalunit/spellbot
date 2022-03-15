from __future__ import annotations

from typing import Any, Optional

from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from ..database import DatabaseSession
from ..models import Config


class ConfigsService:
    def _select(self, guild_xid: int, user_xid: int) -> Optional[dict[str, Any]]:
        config = (
            DatabaseSession.query(Config)
            .filter(
                and_(
                    Config.guild_xid == guild_xid,
                    Config.user_xid == user_xid,
                ),
            )
            .one_or_none()
        )
        return config.to_dict() if config else None

    @sync_to_async
    def upsert(
        self,
        guild_xid: int,
        user_xid: int,
        power_level: Optional[int] = None,
    ) -> dict[str, Any]:
        values = {
            "user_xid": user_xid,
            "guild_xid": guild_xid,
            "power_level": power_level,
        }
        upsert = insert(Config).values(**values)
        upsert = upsert.on_conflict_do_update(
            constraint="configs_pkey",
            index_where=and_(
                Config.guild_xid == values["guild_xid"],
                Config.user_xid == values["user_xid"],
            ),
            set_=dict(power_level=upsert.excluded.power_level),
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()
        data = self._select(guild_xid, user_xid)
        assert data is not None
        return data
