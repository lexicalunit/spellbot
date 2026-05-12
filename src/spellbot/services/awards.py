from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.sql.expression import and_, or_

from spellbot.database import DatabaseSession
from spellbot.models import Game, GuildAward, Play, UserAward, Verify


class NewAward(NamedTuple):
    role: str
    message: str
    remove: bool


async def give_awards(
    guild_xid: int,
    player_xids: list[int],
) -> dict[int, list[NewAward]]:
    new_roles: dict[int, list[NewAward]] = defaultdict(list)

    for player_xid in player_xids:
        plays_result = await DatabaseSession.execute(
            select(func.count())
            .select_from(Game)
            .join(Play)
            .where(
                and_(
                    Game.guild_xid == guild_xid,
                    Play.user_xid == player_xid,
                ),
            ),
        )
        plays = plays_result.scalar() or 0
        if not plays:
            continue

        verified_result = await DatabaseSession.execute(
            select(Verify.verified).where(
                Verify.user_xid == player_xid,
                Verify.guild_xid == guild_xid,
            ),
        )
        verified = bool(verified_result.scalar())

        user_award_result = await DatabaseSession.execute(
            select(UserAward).where(
                and_(
                    UserAward.guild_xid == guild_xid,
                    UserAward.user_xid == player_xid,
                ),
            ),
        )
        user_award = user_award_result.scalar_one_or_none()
        if not user_award:
            continue

        next_awards_result = await DatabaseSession.execute(
            select(GuildAward).where(
                GuildAward.guild_xid == guild_xid,
                or_(
                    GuildAward.count == plays,
                    and_(
                        plays % GuildAward.count == 0,
                        GuildAward.repeating.is_(True),
                    ),
                ),
            ),
        )
        next_awards = next_awards_result.scalars().all()
        for next_award in next_awards:
            if (user_award.guild_award_id != next_award.id) or (
                user_award.guild_award_id == next_award.id and next_award.repeating
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
    await DatabaseSession.commit()

    return new_roles
