# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import PlayData


def generate_pin() -> str:
    return "".join(secrets.choice("0123456789") for i in range(6))


class Play(Base):
    """Records of a users game plays."""

    __tablename__ = "plays"

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this play was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this play was last updated",
    )
    user_xid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        doc="The external Discord ID of the user who played this game",
    )
    game_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
        doc="The SpellBot game ID of the game the user played",
    )
    og_guild_xid: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="The external Discord ID of the guild where the user entered this game",
    )
    pin: Mapped[str | None] = mapped_column(
        String(6),
        nullable=True,
        default=generate_pin,
        doc="A generated PIN for users to identify this game",
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        doc="UTC timestamp when this play's PIN was verified",
    )

    def to_data(self) -> PlayData:
        from spellbot.data import PlayData  # allow_inline

        return PlayData(
            created_at=self.created_at,
            updated_at=self.updated_at,
            user_xid=self.user_xid,
            game_id=self.game_id,
            og_guild_xid=self.og_guild_xid,
            pin=self.pin,
            verified_at=self.verified_at,
        )
