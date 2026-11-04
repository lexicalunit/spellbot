# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

from sqlalchemy import func, select

from spellbot.database import DatabaseSession, any_of
from spellbot.models import Game, GuildAward, Play, UserAward


class NewAward(NamedTuple):
    role: str
    message: str
    remove: bool


def earns(award: GuildAward, plays: int) -> bool:
    """Whether `plays` games earns this award: at its count, or each multiple if it repeats."""
    if award.count == plays:
        return True
    return award.repeating and award.count > 0 and plays % award.count == 0


async def give_awards(
    guild_xid: int,
    player_xids: list[int],
) -> dict[int, list[NewAward]]:
    """
    Return dict of discord user ids -> role names to assign to that user.

    Runs three queries however many players there are: play counts, the players' user
    awards, and the guild's awards.
    """
    new_roles: dict[int, list[NewAward]] = defaultdict(list)

    counts_result = await DatabaseSession.execute(
        select(Play.user_xid, func.count())
        .select_from(Game)
        .join(Play)
        .where(Game.guild_xid == guild_xid, any_of(Play.user_xid, player_xids))
        .group_by(Play.user_xid),
    )
    play_counts: dict[int, int] = dict(counts_result.all())
    user_awards_result = await DatabaseSession.execute(
        select(UserAward).where(
            UserAward.guild_xid == guild_xid,
            any_of(UserAward.user_xid, player_xids),
        ),
    )
    user_awards = {award.user_xid: award for award in user_awards_result.scalars()}
    guild_awards_result = await DatabaseSession.execute(
        select(GuildAward).where(GuildAward.guild_xid == guild_xid).order_by(GuildAward.id),
    )
    guild_awards = guild_awards_result.scalars().all()

    for player_xid in player_xids:
        plays = play_counts.get(player_xid, 0)
        user_award = user_awards.get(player_xid)
        if not plays or not user_award:
            continue
        for next_award in guild_awards:
            if not earns(next_award, plays):
                continue
            if (user_award.guild_award_id != next_award.id) or (
                user_award.guild_award_id == next_award.id and next_award.repeating
            ):
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
