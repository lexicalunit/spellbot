from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.models import Verify

if TYPE_CHECKING:
    from spellbot.data import VerifyData


class VerifiesService:
    async def upsert(
        self,
        guild_xid: int,
        user_xid: int,
        verified: bool | None = None,
    ) -> VerifyData:
        values: dict[str, object] = {
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
                set_={"verified": upsert.excluded.verified},
            )
        await DatabaseSession.execute(upsert, values)
        await DatabaseSession.commit()
        result = await DatabaseSession.execute(
            select(Verify).where(
                and_(Verify.guild_xid == guild_xid, Verify.user_xid == user_xid),
            ),
        )
        record = result.scalar_one_or_none()
        assert record is not None
        return record.to_data()
