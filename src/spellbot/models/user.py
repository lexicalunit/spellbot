# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, now

if TYPE_CHECKING:
    from . import Play, Queue


class User(Base):
    """Represents a Discord user."""

    __tablename__ = "users"

    xid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of this user",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this user was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this user was last updated",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Most recently cached name of this user",
    )
    banned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this user is banned from using SpellBot",
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        doc="If true, this user can access the admin dashboard",
    )
    playgroup_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        doc="The Playgroup Live user ID linked to this Discord user",
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        server_default="en",
        doc="The user's preferred locale from Discord interactions",
    )

    queues: Mapped[list["Queue"]] = relationship(
        "Queue",
        primaryjoin="User.xid == Queue.user_xid",
        doc="Queues this user is currently in",
    )
    plays: Mapped[list["Play"]] = relationship(
        "Play",
        primaryjoin="User.xid == Play.user_xid",
        doc="Queryset of games played by this user",
    )
