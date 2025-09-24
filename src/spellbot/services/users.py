from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from asgiref.sync import sync_to_async
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.models import Block, Game, Play, Post, Queue, User, UserAward, UserDict, Verify, Watch

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)


class UsersService:
    user: User | None = None

    @sync_to_async()
    def upsert(self, target: discord.User | discord.Member) -> UserDict:
        assert hasattr(target, "id")
        xid = target.id
        max_name_len = User.name.property.columns[0].type.length  # type: ignore
        raw_name = getattr(target, "display_name", "")
        name = raw_name[:max_name_len]
        values = {"xid": xid, "name": name, "updated_at": datetime.now(tz=UTC)}
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
        self.user = DatabaseSession.get(User, xid)
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
            "updated_at": datetime.now(tz=UTC),
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
    def current_game_id(self, channel_xid: int) -> int | None:
        """Get the current PENDING game ID for the user in the given channel."""
        assert self.user
        queue = (
            DatabaseSession.query(Queue)
            .join(Game)
            .join(Post)
            .filter(
                and_(
                    Queue.user_xid == self.user.xid,
                    Post.channel_xid == channel_xid,
                ),
            )
            .first()
        )
        return queue.game_id if queue else None

    @sync_to_async()
    def leave_game(self, channel_xid: int) -> None:
        assert self.user
        pending_games = (
            DatabaseSession.query(Queue)
            .join(Game)
            .join(Post)
            .filter(
                and_(
                    Queue.user_xid == self.user.xid,
                    Post.channel_xid == channel_xid,
                ),
            )
        )
        left_game_ids = [game.game_id for game in pending_games]

        DatabaseSession.query(Queue).filter(
            Queue.user_xid == self.user.xid,
            Queue.game_id.in_(left_game_ids),
        ).delete()
        DatabaseSession.commit()

        # This operation should "dirty" the Games, so
        # we need to update their updated_at field now.
        query = (
            update(Game)  # type: ignore
            .where(Game.id.in_(left_game_ids))
            .values(updated_at=datetime.now(tz=UTC))
            .execution_options(synchronize_session=False)
        )
        DatabaseSession.execute(query)
        DatabaseSession.commit()

    @sync_to_async()
    def is_waiting(self, channel_xid: int) -> bool:
        assert self.user
        return self.user.waiting(channel_xid)

    @sync_to_async()
    def pending_games(self) -> int:
        assert self.user
        return self.user.pending_games()

    @sync_to_async()
    def is_banned(self, target_xid: int | None = None) -> bool:
        if target_xid is not None:
            row = DatabaseSession.query(User.banned).filter(User.xid == target_xid).one_or_none()
            return bool(row[0]) if row else False

        assert self.user
        return cast("bool", self.user.banned)

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
    def watch(self, guild_xid: int, user_xid: int, note: str | None = None) -> None:
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

    @sync_to_async()
    def blocklist(self, user_xid: int) -> list[UserDict]:
        return [
            u.to_dict()
            for u in DatabaseSession.query(User)
            .join(Block, User.xid == Block.blocked_user_xid)
            .filter(Block.user_xid == user_xid)
            .order_by(User.xid)
            .all()
        ]

    @sync_to_async()
    def move_user(  # pragma: no cover
        self,
        guild_xid: int,
        from_user_xid: int,
        to_user_xid: int,
    ) -> str | None:
        from_user = DatabaseSession.query(User).filter(User.xid == from_user_xid).one_or_none()
        if not from_user:
            return "user not found"

        if DatabaseSession.query(Queue).filter(Queue.user_xid == from_user_xid).count() > 0:
            return "user is queued"

        try:
            # upsert new user
            user_values = {
                "xid": to_user_xid,
                "name": from_user.name,
                "banned": from_user.banned,
            }
            logger.info("upsert user: %s", user_values)
            user_upsert = insert(User).values(**user_values)
            user_upsert = user_upsert.on_conflict_do_update(
                index_elements=[User.xid],
                index_where=User.xid == user_values["xid"],
                set_={
                    "name": user_upsert.excluded.name,
                    "updated_at": user_upsert.excluded.updated_at,
                    "banned": user_upsert.excluded.banned,
                },
            )
            DatabaseSession.execute(user_upsert, user_values)

            # upsert watches
            for watch in DatabaseSession.query(Watch).filter(
                Watch.user_xid == from_user_xid,
                Watch.guild_xid == guild_xid,
            ):
                watch_values = {
                    "guild_xid": watch.guild_xid,
                    "user_xid": to_user_xid,
                    "note": watch.note,
                }
                logger.info("upsert watch: %s", watch_values)
                watch_upsert = insert(Watch).values(**watch_values)
                watch_upsert = watch_upsert.on_conflict_do_update(
                    index_elements=[Watch.guild_xid, Watch.user_xid],
                    index_where=and_(
                        Watch.guild_xid == watch_values["guild_xid"],
                        Watch.user_xid == watch_values["user_xid"],
                    ),
                    set_={
                        "user_xid": to_user_xid,
                        "note": watch_upsert.excluded.note,
                    },
                )
                DatabaseSession.execute(watch_upsert, watch_values)

            # upsert user blocks
            for user_block in DatabaseSession.query(Block).filter(
                Block.user_xid == from_user_xid,
            ):
                user_block_values = {
                    "user_xid": to_user_xid,
                    "blocked_user_xid": user_block.blocked_user_xid,
                }
                logger.info("upsert block: %s", user_block_values)
                user_block_upsert = insert(Block).values(**user_block_values)
                user_block_upsert = user_block_upsert.on_conflict_do_nothing()
                DatabaseSession.execute(user_block_upsert, user_block_values)

            # upsert user blocked by
            for user_blocked in DatabaseSession.query(Block).filter(
                Block.blocked_user_xid == from_user_xid,
            ):
                user_blocked_values = {
                    "user_xid": user_blocked.user_xid,
                    "blocked_user_xid": to_user_xid,
                }
                logger.info("upsert blocked: %s", user_blocked_values)
                user_blocked_upsert = insert(Block).values(**user_blocked_values)
                user_blocked_upsert = user_blocked_upsert.on_conflict_do_nothing()
                DatabaseSession.execute(user_blocked_upsert, user_blocked_values)

            # upsert verifies
            for verify in DatabaseSession.query(Verify).filter(
                Verify.guild_xid == guild_xid,
                Verify.user_xid == from_user_xid,
            ):
                verify_values = {
                    "guild_xid": verify.guild_xid,
                    "user_xid": to_user_xid,
                    "verified": verify.verified,
                }
                logger.info("upsert verify: %s", verify_values)
                verify_upsert = insert(Verify).values(**verify_values)
                verify_upsert = verify_upsert.on_conflict_do_update(
                    index_elements=[Verify.guild_xid, Verify.user_xid],
                    index_where=and_(
                        Verify.guild_xid == verify_values["guild_xid"],
                        Verify.user_xid == verify_values["user_xid"],
                    ),
                    set_={
                        "user_xid": to_user_xid,
                        "verified": verify_upsert.excluded.verified,
                    },
                )
                DatabaseSession.execute(verify_upsert, verify_values)

            # upsert plays
            for play in (
                DatabaseSession.query(Play)
                .join(Game)
                .filter(
                    Play.user_xid == from_user_xid,
                    Game.guild_xid == guild_xid,
                )
            ):
                play_values = {
                    "user_xid": to_user_xid,
                    "game_id": play.game_id,
                }
                logger.info("upsert play: %s", play_values)
                play_upsert = insert(Play).values(**play_values)
                play_upsert = play_upsert.on_conflict_do_update(
                    index_elements=[Play.user_xid, Play.game_id],
                    index_where=and_(
                        Play.user_xid == play_values["user_xid"],
                        Play.game_id == play_values["game_id"],
                    ),
                    set_={
                        "user_xid": to_user_xid,
                    },
                )
                DatabaseSession.execute(play_upsert, play_values)

            # upsert user awards
            for award in DatabaseSession.query(UserAward).filter(
                UserAward.user_xid == from_user_xid,
                UserAward.guild_xid == guild_xid,
            ):
                award_values = {
                    "user_xid": to_user_xid,
                    "guild_xid": award.guild_xid,
                    "guild_award_id": award.guild_award_id,
                }
                logger.info("upsert award: %s", award_values)
                award_upsert = insert(UserAward).values(**award_values)
                award_upsert = award_upsert.on_conflict_do_update(
                    index_elements=[UserAward.user_xid, UserAward.guild_xid],
                    index_where=and_(
                        UserAward.user_xid == award_values["user_xid"],
                        UserAward.guild_xid == award_values["guild_xid"],
                    ),
                    set_={
                        "user_xid": to_user_xid,
                        "guild_award_id": award_upsert.excluded.guild_award_id,
                    },
                )
                DatabaseSession.execute(award_upsert, award_values)

            DatabaseSession.commit()
        except Exception:
            logger.exception("error moving user")
            DatabaseSession.rollback()
            return "database error"

        return None

    @sync_to_async()
    def get_players_by_xid(self, xids: list[int]) -> list[UserDict]:
        return [u.to_dict() for u in DatabaseSession.query(User).filter(User.xid.in_(xids)).all()]
