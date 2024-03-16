from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

from asgiref.sync import sync_to_async
from sqlalchemy.sql.expression import and_, or_

from spellbot.database import DatabaseSession
from spellbot.models import Game, GuildAward, Play, UserAward, Verify


class NewAward(NamedTuple):
    role: str
    message: str
    remove: bool


class AwardsService:
    @sync_to_async()
    def give_awards(self, guild_xid: int, player_xids: list[int]) -> dict[int, list[NewAward]]:
        """Return dict of discord user ids -> role names to assign to that user."""
        new_roles: dict[int, list[NewAward]] = defaultdict(list)

        for player_xid in player_xids:
            plays = (
                DatabaseSession.query(Game)
                .join(Play)
                .filter(
                    and_(
                        Game.guild_xid == guild_xid,
                        Play.user_xid == player_xid,
                    ),
                )
                .count()
            )
            if not plays:
                continue

            verified = (
                DatabaseSession.query(Verify.verified)
                .filter(
                    Verify.user_xid == player_xid,
                    Verify.guild_xid == guild_xid,
                )
                .scalar()
            )
            verified = bool(verified)  # because it could be None

            user_award = (
                DatabaseSession.query(UserAward)
                .filter(
                    and_(
                        UserAward.guild_xid == guild_xid,
                        UserAward.user_xid == player_xid,
                    ),
                )
                .one_or_none()
            )
            if not user_award:
                continue

            award_q = DatabaseSession.query(GuildAward).filter(
                GuildAward.guild_xid == guild_xid,
            )
            if plays > 0:
                next_awards = award_q.filter(
                    or_(
                        GuildAward.count == plays,
                        and_(
                            plays % GuildAward.count == 0,
                            GuildAward.repeating.is_(True),
                        ),
                    ),
                ).all()
                for next_award in next_awards:
                    if next_award and (
                        (user_award.guild_award_id != next_award.id)
                        or (user_award.guild_award_id == next_award.id and next_award.repeating)
                    ):
                        if next_award.unverified_only and verified:
                            continue
                        if next_award.verified_only and not verified:
                            continue
                        new_roles[player_xid].append(
                            NewAward(
                                next_award.role,
                                next_award.message,
                                next_award.remove,
                            ),
                        )
                        user_award.guild_award_id = next_award.id
        DatabaseSession.commit()

        return new_roles
