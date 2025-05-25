from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TypedDict

from sqlalchemy import Column, DateTime, Integer, String

from . import Base, now


class TokenDict(TypedDict):
    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    key: str


class Token(Base):
    """Token keys for access to the SpellBot API."""

    __tablename__ = "token"

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

    def to_dict(self) -> TokenDict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
            "key": self.key,
        }
