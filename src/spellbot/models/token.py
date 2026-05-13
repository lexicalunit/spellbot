from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Integer, String, text

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import TokenData


class Token(Base):
    """Token keys for access to the SpellBot API."""

    __tablename__ = "tokens"

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="A pk for this token",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this key was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this key was last updated",
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this key was deleted",
    )
    key = Column(
        String,
        nullable=False,
        index=True,
        doc="The API token key",
    )
    note = Column(
        String,
        nullable=True,
        doc="A note for my reference",
    )
    scopes = Column(
        String,
        nullable=False,
        default="*",
        server_default=text("'*'"),
        doc="A comma-separated list of scopes for this token",
    )

    def to_data(self) -> TokenData:
        from spellbot.data import TokenData  # allow_inline

        return TokenData(
            id=self.id,  # type: ignore
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            deleted_at=self.deleted_at,  # type: ignore
            key=self.key,  # type: ignore
            note=self.note,  # type: ignore
            scopes=self.scopes,  # type: ignore
        )
