from datetime import datetime
from typing import Optional

import discord
from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.models.award import GuildAward
from spellbot.models.guild import Guild
from spellbot.services import BaseService


class GuildsService(BaseService):
    def __init__(self):
        self.guild: Optional[Guild] = None

    @sync_to_async()
    def upsert(self, guild: discord.Guild) -> None:
        name = guild.name[: Guild.name.property.columns[0].type.length]  # type: ignore
        values = {
            "xid": guild.id,
            "name": name,
            "updated_at": datetime.utcnow(),
        }
        upsert = insert(Guild).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Guild.xid],
            index_where=Guild.xid == values["xid"],
            set_=dict(
                name=upsert.excluded.name,
                updated_at=upsert.excluded.updated_at,
            ),
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()
        self.guild = (
            DatabaseSession.query(Guild)
            .filter(
                Guild.xid == guild.id,
            )
            .one_or_none()
        )

    @sync_to_async
    def select(self, guild_xid: int) -> bool:
        self.guild = (
            DatabaseSession.query(Guild)
            .filter(
                Guild.xid == guild_xid,
            )
            .one_or_none()
        )
        return bool(self.guild)

    @sync_to_async()
    def should_voice_create(self) -> bool:
        assert self.guild
        return self.guild.voice_create

    @sync_to_async()
    def should_show_points(self) -> bool:
        assert self.guild
        return self.guild.show_points

    @sync_to_async()
    def set_motd(self, message: str) -> None:
        assert self.guild
        motd = message[: Guild.motd.property.columns[0].type.length]  # type: ignore
        self.guild.motd = motd  # type: ignore
        DatabaseSession.commit()

    @sync_to_async()
    def toggle_show_links(self) -> None:
        assert self.guild
        self.guild.show_links = not self.guild.show_links  # type: ignore
        DatabaseSession.commit()

    @sync_to_async()
    def toggle_show_points(self) -> None:
        assert self.guild
        self.guild.show_points = not self.guild.show_points  # type: ignore
        DatabaseSession.commit()

    @sync_to_async()
    def toggle_voice_create(self) -> None:
        assert self.guild
        self.guild.voice_create = not self.guild.voice_create  # type: ignore
        DatabaseSession.commit()

    @sync_to_async
    def current_name(self) -> str:
        assert self.guild
        return self.guild.name or ""

    @sync_to_async
    def voiced(self) -> list[int]:
        rows = DatabaseSession.query(Guild.xid).filter(Guild.voice_create.is_(True)).all()
        if not rows:
            return []
        return [int(row[0]) for row in rows]

    @sync_to_async
    def to_dict(self) -> dict:
        assert self.guild
        return self.guild.to_dict()

    @sync_to_async
    def has_award_with_count(self, count: int) -> bool:
        assert self.guild
        return bool(
            DatabaseSession.query(GuildAward)
            .filter(
                and_(
                    GuildAward.guild_xid == self.guild.xid,
                    GuildAward.count == count,
                )
            )
            .one_or_none()
        )

    @sync_to_async
    def award_add(
        self,
        count: int,
        role: str,
        message: str,
        repeating: Optional[bool] = False,
    ) -> int:
        assert self.guild
        award = GuildAward(
            guild_xid=self.guild.xid,
            count=count,
            role=role,
            message=message,
            repeating=repeating,
        )  # type: ignore
        DatabaseSession.add(award)
        DatabaseSession.commit()
        return award.id

    @sync_to_async
    def award_delete(self, guild_award_id: int):
        assert self.guild
        award = DatabaseSession.query(GuildAward).get(guild_award_id)
        if award:
            DatabaseSession.delete(award)
        DatabaseSession.commit()