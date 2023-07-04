from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

import discord
import pytz
from asgiref.sync import sync_to_async
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from ..database import DatabaseSession
from ..models import Block, Game, Queue, User, Watch


class UsersService:
    user: Optional[User] = None

    @sync_to_async()
    def upsert(self, target: Union[discord.User, discord.Member]) -> dict[str, Any]:
        assert hasattr(target, "id")
        xid = target.id  # type: ignore
        max_name_len = User.name.property.columns[0].type.length  # type: ignore
        raw_name = getattr(target, "display_name", "")
        name = raw_name[:max_name_len]
        values = {"xid": xid, "name": name, "updated_at": datetime.now(tz=pytz.utc)}
        upsert = insert(User).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[User.xid],
            index_where=User.xid == values["xid"],
            set_={
                "name": upsert.excluded.name,
                "updated_at": upsert.excluded.updated_at,
            },
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()
        self.user = DatabaseSession.query(User).get(xid)
        assert self.user
        return self.user.to_dict()

    @sync_to_async()
    def select(self, user_xid: int) -> bool:
        self.user = DatabaseSession.query(User).filter(User.xid == user_xid).one_or_none()
        return bool(self.user)

    @sync_to_async()
    def set_banned(self, banned: bool, xid: int) -> None:
        values = {
            "xid": xid,
            "name": "Unknown User",
            "updated_at": datetime.now(tz=pytz.utc),
            "banned": banned,
        }
        upsert = insert(User).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[User.xid],
            index_where=User.xid == values["xid"],
            set_={
                "updated_at": upsert.excluded.updated_at,
                "banned": upsert.excluded.banned,
            },
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async()
    def current_game_id(self, channel_xid: int) -> Optional[int]:
        """Gets the current PENDING game ID for the user in the given channel."""
        assert self.user
        queue = (
            DatabaseSession.query(Queue)
            .join(Game)
            .filter(
                and_(
                    Queue.user_xid == self.user.xid,
                    Game.channel_xid == channel_xid,
                ),
            )
            .first()
        )
        return queue.game_id if queue else None

    @sync_to_async()
    def leave_game(self, channel_xid: int) -> Optional[int]:
        assert self.user
        game = self.user.game(channel_xid)
        left_game_id = game.id if game else None

        if left_game_id is not None:
            inner = (
                select(Game.id)  # type: ignore
                .join(Queue)
                .filter(  # type: ignore
                    and_(
                        Queue.user_xid == self.user.xid,
                        Game.channel_xid == channel_xid,
                    ),
                )
            )
            DatabaseSession.query(Queue).filter(
                and_(
                    Queue.user_xid == self.user.xid,
                    Queue.game_id.in_(inner),
                ),
            ).delete()
            DatabaseSession.commit()

            # This operation should "dirty" the Game, so
            # we need to update its updated_at field now.
            query = (
                update(Game)
                .where(Game.id == left_game_id)
                .values(updated_at=datetime.now(tz=pytz.utc))
                .execution_options(synchronize_session=False)
            )
            DatabaseSession.execute(query)
            DatabaseSession.commit()

        return left_game_id

    @sync_to_async()
    def is_waiting(self, channel_xid: int) -> bool:
        assert self.user
        return self.user.waiting(channel_xid)

    @sync_to_async()
    def queued_in_another_guild(self, guild_xid: int) -> bool:
        assert self.user
        return bool(
            DatabaseSession.query(Queue)
            .join(Game, Queue.game_id == Game.id)
            .filter(
                Queue.user_xid == self.user.xid,
                Game.guild_xid != guild_xid,
            )
            .count(),
        )

    @sync_to_async()
    def pending_games(self) -> int:
        assert self.user
        return self.user.pending_games()

    @sync_to_async()
    def is_banned(self, target_xid: Optional[int] = None) -> bool:
        if target_xid is not None:
            row = DatabaseSession.query(User.banned).filter(User.xid == target_xid).one_or_none()
            return bool(row[0]) if row else False

        assert self.user
        return self.user.banned

    @sync_to_async()
    def block(self, author_xid: int, target_xid: int) -> None:
        values = {
            "user_xid": author_xid,
            "blocked_user_xid": target_xid,
        }
        upsert = insert(Block).values(**values)
        upsert = upsert.on_conflict_do_nothing()
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async()
    def unblock(self, author_xid: int, target_xid: int) -> None:
        DatabaseSession.query(Block).filter(
            and_(
                Block.user_xid == author_xid,
                Block.blocked_user_xid == target_xid,
            ),
        ).delete(synchronize_session=False)
        DatabaseSession.commit()

    @sync_to_async()
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
                set_={"note": upsert.excluded.note},
            )
        else:
            upsert = upsert.on_conflict_do_nothing()
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async()
    def unwatch(self, guild_xid: int, user_xid: int) -> None:
        DatabaseSession.query(Watch).filter(
            and_(
                Watch.guild_xid == guild_xid,
                Watch.user_xid == user_xid,
            ),
        ).delete(synchronize_session=False)
        DatabaseSession.commit()
