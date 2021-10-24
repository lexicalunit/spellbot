from datetime import datetime
from typing import Any, Optional, Union

import discord
from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.models.block import Block
from spellbot.models.user import User
from spellbot.models.watch import Watch
from spellbot.services import BaseService


class UsersService(BaseService):
    def __init__(self):
        self.user: Optional[User] = None

    @sync_to_async
    def upsert(self, target: Union[discord.User, discord.Member]) -> dict:
        assert hasattr(target, "id")
        xid = target.id  # type: ignore
        name = target.display_name
        max_name_len = User.name.property.columns[0].type.length  # type: ignore
        values = {
            "xid": xid,
            "name": name[:max_name_len],
            "updated_at": datetime.utcnow(),
        }
        upsert = insert(User).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[User.xid],
            index_where=User.xid == values["xid"],
            set_=dict(
                name=upsert.excluded.name,
                updated_at=upsert.excluded.updated_at,
            ),
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()
        self.user = DatabaseSession.query(User).get(xid)
        assert self.user
        return self.user.to_dict()

    @sync_to_async
    def select(self, user_xid: int) -> bool:
        self.user = DatabaseSession.query(User).filter(User.xid == user_xid).one_or_none()
        return bool(self.user)

    @sync_to_async
    def set_banned(self, banned: bool, xid: int) -> None:
        values = {
            "xid": xid,
            "name": "Unknown User",
            "updated_at": datetime.utcnow(),
            "banned": banned,
        }
        upsert = insert(User).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[User.xid],
            index_where=User.xid == values["xid"],
            set_=dict(
                updated_at=upsert.excluded.updated_at,
                banned=upsert.excluded.banned,
            ),
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async
    def current_game_id(self) -> Optional[int]:
        assert self.user
        return self.user.game_id

    @sync_to_async
    def leave_game(self) -> None:
        assert self.user
        assert self.user.game
        self.user.game_id = None  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def is_waiting(self) -> bool:
        assert self.user
        return self.user.waiting

    @sync_to_async
    def is_banned(self, target_xid: Optional[int] = None) -> bool:
        if target_xid is not None:
            row = (
                DatabaseSession.query(User.banned)
                .filter(User.xid == target_xid)
                .one_or_none()
            )
            return bool(row[0]) if row else False

        assert self.user
        return self.user.banned

    @sync_to_async
    def block(self, author_xid: int, target_xid: int) -> None:
        values = {
            "user_xid": author_xid,
            "blocked_user_xid": target_xid,
        }
        upsert = insert(Block).values(**values)
        upsert = upsert.on_conflict_do_nothing()
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async
    def unblock(self, author_xid: int, target_xid: int) -> None:
        DatabaseSession.query(Block).filter(
            and_(
                Block.user_xid == author_xid,
                Block.blocked_user_xid == target_xid,
            )
        ).delete(synchronize_session=False)
        DatabaseSession.commit()

    @sync_to_async
    def watch(self, guild_xid: int, user_xid: int, note: Optional[str] = None) -> None:
        values: dict[str, Any] = {
            "guild_xid": guild_xid,
            "user_xid": user_xid,
        }
        upsert = insert(Watch).values(**values)
        if note:
            max_note_len = Watch.note.property.columns[0].type.length  # type: ignore
            values["note"] = note[:max_note_len]
            upsert = upsert.on_conflict_do_update(
                constraint="watches_pkey",
                index_where=and_(
                    Watch.guild_xid == values["guild_xid"],
                    Watch.user_xid == values["user_xid"],
                ),
                set_=dict(note=upsert.excluded.note),
            )
        else:
            upsert = upsert.on_conflict_do_nothing()
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async
    def unwatch(self, guild_xid: int, user_xid: int) -> None:
        DatabaseSession.query(Watch).filter(
            and_(
                Watch.guild_xid == guild_xid,
                Watch.user_xid == user_xid,
            )
        ).delete(synchronize_session=False)
        DatabaseSession.commit()
