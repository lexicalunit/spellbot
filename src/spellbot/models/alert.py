from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.expression import text

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import AlertData


class Alert(Base):
    """Notification preferences for a user in a guild."""

    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("guild_xid", "user_xid", name="uq_alerts_guild_user"),)

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The ID used to refer to this alert",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this alert was first created",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this alert was last updated",
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        doc="UTC timestamp when this alert was deleted",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The external Discord ID of the guild these preferences apply to",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The external Discord ID of the user these preferences belong to",
    )
    preferences = cast(
        "dict[str, Any]",
        Column(
            JSONB,
            nullable=False,
            default=dict,
            server_default=text("'{}'::jsonb"),
            doc="JSON object describing the user's notification preferences",
        ),
    )

    def to_data(self) -> AlertData:
        from spellbot.data import AlertData  # allow_inline

        prefs = self.preferences or {}
        active_hours = prefs.get("active_hours")
        return AlertData(
            id=self.id,  # type: ignore
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            guild_xid=self.guild_xid,  # type: ignore
            user_xid=self.user_xid,  # type: ignore
            formats=list(prefs.get("formats") or []),
            brackets=list(prefs.get("brackets") or []),
            channels=list(prefs.get("channels") or []),
            active_hours=dict(active_hours) if active_hours else None,
            deleted_at=self.deleted_at,  # type: ignore
        )
