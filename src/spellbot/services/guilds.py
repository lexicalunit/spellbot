from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from asgiref.sync import sync_to_async
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.environment import running_in_pytest
from spellbot.models import Channel, Guild, GuildAward, GuildAwardDict, GuildDict

if TYPE_CHECKING:
    import discord

guild_cache: dict[int, str] = {}


def is_cached(xid: int, name: str) -> bool:  # pragma: no cover
    if running_in_pytest():
        return False
    return bool((cached_name := guild_cache.get(xid)) and cached_name == name)


class GuildsService:
    guild: Guild | None = None

    @sync_to_async()
    def upsert(self, guild: discord.Guild) -> GuildDict | None:
        name_max_len = Guild.name.property.columns[0].type.length  # type: ignore
        raw_name = getattr(guild, "name", "")
        name = raw_name[:name_max_len]
        if not is_cached(guild.id, name):
            values = {
                "xid": guild.id,
                "name": name,
                "updated_at": datetime.now(tz=UTC),
            }
            upsert = insert(Guild).values(**values)
            upsert = upsert.on_conflict_do_update(
                index_elements=[Guild.xid],
                index_where=Guild.xid == values["xid"],
                set_={
                    "name": upsert.excluded.name,
                    "updated_at": upsert.excluded.updated_at,
                },
                where=upsert.excluded.name != Guild.name,
            )
            DatabaseSession.execute(upsert, values)
            DatabaseSession.commit()
            guild_cache[guild.id] = name

        self.guild = DatabaseSession.query(Guild).filter(Guild.xid == guild.id).one_or_none()
        return self.guild.to_dict() if self.guild else None

    @sync_to_async()
    def set_banned(self, banned: bool, xid: int) -> None:
        values = {
            "xid": xid,
            "name": "Unknown Guild",
            "updated_at": datetime.now(tz=UTC),
            "banned": banned,
        }
        upsert = insert(Guild).values(**values)
        upsert = upsert.on_conflict_do_update(
            index_elements=[Guild.xid],
            index_where=Guild.xid == values["xid"],
            set_={
                "updated_at": upsert.excluded.updated_at,
                "banned": upsert.excluded.banned,
            },
        )
        DatabaseSession.execute(upsert, values)
        DatabaseSession.commit()

    @sync_to_async()
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
        return cast("bool", self.guild.voice_create)

    @sync_to_async()
    def get_use_max_bitrate(self) -> bool:
        assert self.guild
        return cast("bool", self.guild.use_max_bitrate)

    @sync_to_async()
    def set_suggest_vc_category(self, category: str | None) -> None:
        assert self.guild
        self.guild.suggest_voice_category = category
        DatabaseSession.commit()

    @sync_to_async()
    def set_motd(self, message: str | None = None) -> None:
        if message:
            motd = message[: Guild.motd.property.columns[0].type.length]  # type: ignore
            self.guild.motd = motd  # type: ignore
        else:
            self.guild.motd = ""  # type: ignore
        DatabaseSession.commit()

    @sync_to_async()
    def toggle_show_links(self) -> None:
        assert self.guild
        self.guild.show_links = not self.guild.show_links
        DatabaseSession.commit()

    @sync_to_async()
    def toggle_voice_create(self) -> None:
        assert self.guild
        self.guild.voice_create = not self.guild.voice_create
        if self.guild.voice_create:
            self.guild.suggest_voice_category = None
        DatabaseSession.commit()

    @sync_to_async()
    def toggle_use_max_bitrate(self) -> None:
        assert self.guild
        self.guild.use_max_bitrate = not self.guild.use_max_bitrate
        DatabaseSession.commit()

    @sync_to_async()
    def current_name(self) -> str:
        assert self.guild
        return cast("str | None", self.guild.name) or ""

    @sync_to_async()
    def voice_category_prefixes(self) -> list[str]:
        assert self.guild
        return [
            str(row[0])
            for row in DatabaseSession.query(Channel.voice_category)
            .filter(Channel.guild_xid == self.guild.xid)
            .distinct()
            .all()
        ]

    @sync_to_async()
    def voiced(self) -> list[int]:
        rows = DatabaseSession.query(Guild.xid).filter(Guild.voice_create.is_(True)).all()
        if not rows:
            return []
        return [int(row[0]) for row in rows]

    @sync_to_async()
    def to_dict(self) -> GuildDict:
        assert self.guild
        return self.guild.to_dict()

    @sync_to_async()
    def has_award_with_count(self, count: int) -> bool:
        assert self.guild
        return bool(
            DatabaseSession.query(GuildAward)
            .filter(
                and_(
                    GuildAward.guild_xid == self.guild.xid,
                    GuildAward.count == count,
                ),
            )
            .one_or_none(),
        )

    @sync_to_async()
    def award_add(
        self,
        count: int,
        role: str,
        message: str,
        **options: bool | None,
    ) -> GuildAwardDict:
        assert self.guild
        repeating = bool(options.get("repeating", False))
        remove = bool(options.get("remove", False))
        verified_only = bool(options.get("verified_only", False))
        unverified_only = bool(options.get("unverified_only", False))
        award = GuildAward(
            guild_xid=self.guild.xid,
            count=count,
            role=role,
            message=message,
            repeating=repeating,
            remove=remove,
            verified_only=verified_only,
            unverified_only=unverified_only,
        )
        DatabaseSession.add(award)
        DatabaseSession.commit()
        return award.to_dict()

    @sync_to_async()
    def award_delete(self, guild_award_id: int) -> None:
        assert self.guild
        award = DatabaseSession.get(GuildAward, guild_award_id)
        if award:
            DatabaseSession.delete(award)
        DatabaseSession.commit()

    @sync_to_async()
    def setup_mythic_track(self) -> bool:
        assert self.guild
        self.guild.enable_mythic_track = not self.guild.enable_mythic_track
        DatabaseSession.commit()
        return self.guild.enable_mythic_track
