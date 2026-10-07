# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, cast

from sqlalchemy import BigInteger, Boolean, DateTime, String, false, null, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, now, web_editable

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spellbot.data import GuildData

    from . import Channel, Game, GuildAward


class Guild(Base):
    """Represents a Discord guild."""

    __tablename__ = "guilds"

    xid: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this guild was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this guild was last updated",
    )
    name: Mapped[str | None] = mapped_column(
        String(100),
        doc="Most recently cached name of this guild",
    )
    motd: Mapped[str | None] = mapped_column(
        String(255),
        doc=web_editable("The message of the day, shown in all game posts on the server."),
    )
    show_links: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("When enabled the game links will be visible in the channel post."),
    )
    voice_create: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "When enabled the bot will automatically create voice channels for games.",
        ),
    )
    use_max_bitrate: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable(
            "When enabled the bot will create voice channels using the maximum bitrate possible.",
        ),
    )
    banned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this guild is banned from using SpellBot",
    )
    notice: Mapped[str | None] = mapped_column(
        String(255),
        doc="Notice to display to users in this guild",
        nullable=True,
        default=None,
        server_default=null(),
    )
    suggest_voice_category: Mapped[str | None] = mapped_column(
        String(100),
        doc=web_editable("Category to use when suggesting voice channels for games"),
        nullable=True,
        default=None,
        server_default=null(),
    )
    enable_mythic_track: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc=web_editable("If true, enable Mythic Track for this guild."),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        doc="If false, the bot is no longer a member of this guild",
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default="en",
        doc="The guild's preferred locale from Discord",
    )
    icon: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        server_default=null(),
        doc="Cached Discord CDN URL for this guild's icon",
    )
    promote: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        doc="If true, this guild may be advertised on public SpellBot pages",
    )

    games: Mapped[list["Game"]] = relationship(
        "Game",
        back_populates="guild",
        uselist=True,
        doc="Games played on this guild",
    )
    channels: Mapped[list["Channel"]] = relationship(
        "Channel",
        back_populates="guild",
        uselist=True,
        doc="Channels on this guild",
    )
    awards: Mapped[list["GuildAward"]] = relationship(
        "GuildAward",
        back_populates="guild",
        uselist=True,
        order_by="GuildAward.count",
        doc="Awards available in this guild",
    )

    async def to_data(self) -> GuildData:
        from spellbot.data import GuildData  # allow_inline

        channels = await self.awaitable_attrs.channels
        awards = await self.awaitable_attrs.awards
        return GuildData(
            xid=self.xid,
            created_at=self.created_at,
            updated_at=self.updated_at,
            name=self.name,
            motd=self.motd,
            show_links=self.show_links,
            voice_create=self.voice_create,
            use_max_bitrate=self.use_max_bitrate,
            channels=sorted(
                [channel.to_data() for channel in cast("Iterable[Channel]", channels)],
                key=lambda c: c.xid,
            ),
            awards=sorted(
                [award.to_data() for award in cast("Iterable[GuildAward]", awards)],
                key=lambda c: c.id,
            ),
            banned=self.banned,
            notice=self.notice,
            suggest_voice_category=self.suggest_voice_category,
            enable_mythic_track=self.enable_mythic_track,
            active=self.active,
            locale=self.locale,
            icon=self.icon,
            promote=self.promote,
        )
