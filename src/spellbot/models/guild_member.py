# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from . import Base, now


class GuildMember(Base):
    """Tracks user membership within a guild."""

    __tablename__ = "guild_members"

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this membership was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this membership was last updated",
    )
    user_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The external Discord ID of the user",
    )
    guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The external Discord ID of the guild",
    )
    membership_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc=(
            "UTC timestamp when this membership was last confirmed against the Discord API,"
            " or NULL when it never has been"
        ),
    )
