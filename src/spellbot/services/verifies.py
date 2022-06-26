from __future__ import annotations

from typing import Optional

from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from ..database import DatabaseSession
from ..models import Verify


class VerifiesService:
    def __init__(self):
        self.current: Optional[Verify] = None

    @sync_to_async
    def upsert(
        self,
        guild_xid: int,
        user_xid: int,
        verified: Optional[bool] = None,
    ) -> None:
        values = {
            "user_xid": user_xid,
            "guild_xid": guild_xid,
        }
        if verified is not None:
            values["verified"] = verified
        upsert = insert(Verify).values(**values)
        if verified is None:
            upsert = upsert.on_conflict_do_nothing()
        else:
            upsert = upsert.on_conflict_do_update(
                constraint="verify_pkey",
                index_where=and_(
                    Verify.guild_xid == values["guild_xid"],
                    Verify.user_xid == values["user_xid"],
                ),
                set_=dict(verified=upsert.excluded.verified),
            )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()
        self.current = (
            DatabaseSession.query(Verify)
            .filter(
                and_(
                    Verify.guild_xid == guild_xid,
                    Verify.user_xid == user_xid,
                ),
            )
            .one_or_none()
        )

    @sync_to_async
    def is_verified(self) -> bool:
        assert self.current
        return bool(self.current.verified)
