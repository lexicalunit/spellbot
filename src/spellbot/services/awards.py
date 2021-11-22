# pylint: disable=wrong-import-order

from collections import namedtuple

from asgiref.sync import sync_to_async
from sqlalchemy.sql.expression import and_, or_

from ..database import DatabaseSession
from ..models import GuildAward, Play, UserAward

NewAward = namedtuple("NewAward", ["role", "message"])


class AwardsService:
    @sync_to_async
    def give_awards(self, guild_xid: int, player_xids: list[int]) -> dict[int, NewAward]:
        """Returns dict of discord user ids -> role names to assign to that user."""
        new_roles: dict[int, NewAward] = {}

        for player_xid in player_xids:
            plays = (
                DatabaseSession.query(Play)
                .filter(
                    Play.user_xid == player_xid,
                )
                .count()
            )
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
            assert user_award

            award_q = DatabaseSession.query(GuildAward).filter(
                GuildAward.guild_xid == guild_xid,
            )
            if plays > 0:
                next_award = award_q.filter(
                    or_(
                        GuildAward.count == plays,
                        and_(
                            plays % GuildAward.count == 0,
                            GuildAward.repeating.is_(True),
                        ),
                    ),
                ).one_or_none()
                if next_award and (
                    (user_award.guild_award_id != next_award.id)
                    or (
                        user_award.guild_award_id == next_award.id
                        and next_award.repeating
                    )
                ):
                    new_roles[player_xid] = NewAward(next_award.role, next_award.message)
                    user_award.guild_award_id = next_award.id  # type: ignore
        DatabaseSession.commit()

        return new_roles
