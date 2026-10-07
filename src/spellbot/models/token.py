# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import TokenData


class Token(Base):
    """Token keys for access to the SpellBot API."""

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="A pk for this token",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this key was first created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this key was last updated",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this key was deleted",
    )
    key: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        doc="The API token key",
    )
    note: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        doc="A note for my reference",
    )
    scopes: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="*",
        server_default=text("'*'"),
        doc="A comma-separated list of scopes for this token",
    )

    def to_data(self) -> TokenData:
        from spellbot.data import TokenData  # allow_inline

        return TokenData(
            id=self.id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
            key=self.key,
            note=self.note,
            scopes=self.scopes,
        )
