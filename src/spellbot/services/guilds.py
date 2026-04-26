from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.environment import running_in_pytest
from spellbot.models import Channel, Guild, GuildAward

if TYPE_CHECKING:
    import discord

    from spellbot.data import GuildAwardData, GuildData


guild_cache: dict[int, str] = {}


def is_cached(xid: int, name: str) -> bool:  # pragma: no cover
    if running_in_pytest():
        return False
    return bool((cached_name := guild_cache.get(xid)) and cached_name == name)


class GuildsService:
    @sync_to_async()
    def upsert(self, guild: discord.Guild) -> GuildData | None:
        """Upsert the given Discord guild into the database."""
        name_max_len = Guild.name.property.columns[0].type.length  # type: ignore
        raw_name = getattr(guild, "name", "")
        name = raw_name[:name_max_len]
        if not is_cached(guild.id, name):  # pragma: no branch (caching disabled in tests)
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

        result = DatabaseSession.query(Guild).filter(Guild.xid == guild.id).one_or_none()
        return result.to_data() if guild else None

    @sync_to_async()
    def set_banned(self, guild_xid: int, banned: bool) -> None:
        """Mark the given guild as banned from using this bot."""
        values = {
            "xid": guild_xid,
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
    def get(self, guild_xid: int) -> GuildData | None:
        """Fetch the guild data for the given guild xid."""
        guild = DatabaseSession.query(Guild).filter(Guild.xid == guild_xid).one_or_none()
        return guild.to_data() if guild else None

    @sync_to_async()
    def set_suggest_vc_category(self, guild_data: GuildData, category: str | None) -> GuildData:
        """Set the suggested voice channel category prefix for the guild."""
        stmt = (
            update(Guild)  # type: ignore
            .where(Guild.xid == guild_data.xid)
            .values(suggest_voice_category=category)
            .returning(Guild)  # type: ignore
        )
        updated_guild: Guild = DatabaseSession.scalars(stmt).one()
        DatabaseSession.commit()
        return updated_guild.to_data()

    @sync_to_async()
    def set_motd(self, guild_data: GuildData, message: str | None = None) -> GuildData:
        """Set the message of the day for the guild."""
        motd = (
            message[: Guild.motd.property.columns[0].type.length]  # type: ignore
            if message
            else ""
        )
        stmt = (
            update(Guild)  # type: ignore
            .where(Guild.xid == guild_data.xid)
            .values(motd=motd)
            .returning(Guild)  # type: ignore
        )
        updated_guild: Guild = DatabaseSession.scalars(stmt).one()
        DatabaseSession.commit()
        return updated_guild.to_data()

    @sync_to_async()
    def toggle_show_links(self, guild_data: GuildData) -> GuildData:
        """Toggle whether to show SpellTable links in game posts."""
        new_value = not guild_data.show_links
        stmt = (
            update(Guild)  # type: ignore
            .where(Guild.xid == guild_data.xid)
            .values(show_links=new_value)
            .returning(Guild)  # type: ignore
        )
        updated_guild: Guild = DatabaseSession.scalars(stmt).one()
        DatabaseSession.commit()
        return updated_guild.to_data()

    @sync_to_async()
    def toggle_voice_create(self, guild_data: GuildData) -> GuildData:
        """Toggle whether to automatically create voice channels for games."""
        new_value = not guild_data.voice_create
        values: dict[str, bool | None] = {"voice_create": new_value}
        if new_value:
            values["suggest_voice_category"] = None
        stmt = (
            update(Guild)  # type: ignore
            .where(Guild.xid == guild_data.xid)
            .values(**values)
            .returning(Guild)  # type: ignore
        )
        updated_guild: Guild = DatabaseSession.scalars(stmt).one()
        DatabaseSession.commit()
        return updated_guild.to_data()

    @sync_to_async()
    def toggle_use_max_bitrate(self, guild_data: GuildData) -> GuildData:
        """Toggle whether to use maximum bitrate for created voice channels."""
        new_value = not guild_data.use_max_bitrate
        stmt = (
            update(Guild)  # type: ignore
            .where(Guild.xid == guild_data.xid)
            .values(use_max_bitrate=new_value)
            .returning(Guild)  # type: ignore
        )
        updated_guild: Guild = DatabaseSession.scalars(stmt).one()
        DatabaseSession.commit()
        return updated_guild.to_data()

    @sync_to_async()
    def voice_category_prefixes(self, guild_xid: int) -> list[str]:
        """Return distinct voice category prefixes configured across all channels."""
        return [
            str(row[0])
            for row in DatabaseSession.query(Channel.voice_category)
            .filter(Channel.guild_xid == guild_xid)
            .distinct()
            .all()
        ]

    @sync_to_async()
    def voiced(self) -> list[int]:
        """Return guild xids that have voice channel creation enabled."""
        rows = DatabaseSession.query(Guild.xid).filter(Guild.voice_create.is_(True)).all()
        if not rows:
            return []
        return [int(row[0]) for row in rows]

    @sync_to_async()
    def has_award_with_count(self, guild_xid: int, count: int) -> bool:
        """Check if the guild has an award configured for the given play count."""
        return bool(
            DatabaseSession.query(GuildAward)
            .filter(
                and_(
                    GuildAward.guild_xid == guild_xid,
                    GuildAward.count == count,
                ),
            )
            .one_or_none(),
        )

    @sync_to_async()
    def award_add(
        self,
        guild_xid: int,
        count: int,
        role: str,
        message: str,
        **options: bool | None,
    ) -> GuildAwardData:
        """Add a new award configuration to the guild."""
        repeating = bool(options.get("repeating", False))
        remove = bool(options.get("remove", False))
        verified_only = bool(options.get("verified_only", False))
        unverified_only = bool(options.get("unverified_only", False))
        award = GuildAward(
            guild_xid=guild_xid,
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
        return award.to_data()

    @sync_to_async()
    def award_delete(self, guild_award_id: int) -> None:
        """Delete the award with the given id."""
        award = DatabaseSession.get(GuildAward, guild_award_id)
        if award:
            DatabaseSession.delete(award)
        DatabaseSession.commit()

    @sync_to_async()
    def setup_mythic_track(self, guild_data: GuildData) -> GuildData:
        """Toggle whether mythic track is enabled for the guild."""
        new_value = not guild_data.enable_mythic_track
        stmt = (
            update(Guild)  # type: ignore
            .where(Guild.xid == guild_data.xid)
            .values(enable_mythic_track=new_value)
            .returning(Guild)  # type: ignore
        )
        updated_guild: Guild = DatabaseSession.scalars(stmt).one()
        DatabaseSession.commit()
        return updated_guild.to_data()
