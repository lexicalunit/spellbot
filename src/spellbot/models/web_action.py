from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.expression import text

from . import Base, now

if TYPE_CHECKING:
    from spellbot.data import WebActionData


class WebActionKind(StrEnum):
    """What a website-initiated action asks the bot to do."""

    CREATE = "create"
    JOIN = "join"
    LEAVE = "leave"


class WebActionStatus(StrEnum):
    """Where a website-initiated action is in its lifecycle."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# Stable error codes recorded on a failed action. The web tier maps these to
# translated messages (`web.play.error.*`); they are never rendered raw.
class WebActionError(StrEnum):
    """Why a website-initiated action could not be carried out."""

    BOT_MISSING_PERMISSIONS = "bot_missing_permissions"
    CHANNEL_UNAVAILABLE = "channel_unavailable"
    CHANNEL_UNVERIFIED_ONLY = "channel_unverified_only"
    CHANNEL_VERIFIED_ONLY = "channel_verified_only"
    EXPIRED = "expired"
    GUILD_BANNED = "guild_banned"
    GUILD_UNAVAILABLE = "guild_unavailable"
    INTERNAL_ERROR = "internal_error"
    MISSING_PERMISSIONS = "missing_permissions"
    NOT_A_MEMBER = "not_a_member"
    REJECTED = "rejected"
    USER_BANNED = "user_banned"
    WEB_GAMES_DISABLED = "web_games_disabled"


class WebAction(Base):
    """
    A request made from the SpellBot website for the bot to act in Discord.

    The bot and the web server are separate processes that share only this database, so
    the website can not call into the running bot. It records what the user asked for
    here instead, and a task loop in the bot process (see `TasksAction.process_web_actions`)
    claims the row and carries it out through the same action code the Discord commands
    use. The website polls for the outcome.
    """

    __tablename__ = "web_actions"
    __table_args__ = (
        # Supports the worker's claim query, which scans for the oldest pending rows.
        Index("ix_web_actions_status_created_at", "status", "created_at"),
    )

    id = Column(
        Integer,
        autoincrement=True,
        nullable=False,
        primary_key=True,
        doc="The ID used to refer to this web action",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        doc="UTC timestamp when this action was requested",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=partial(datetime.now, UTC),
        server_default=now,
        onupdate=partial(datetime.now, UTC),
        doc="UTC timestamp when this action was last updated",
    )
    resolved_at = Column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when this action finished, successfully or not",
    )
    user_xid = Column(
        BigInteger,
        ForeignKey("users.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The external Discord ID of the user who requested this action",
    )
    guild_xid = Column(
        BigInteger,
        ForeignKey("guilds.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The external Discord ID of the guild this action targets",
    )
    channel_xid = Column(
        BigInteger,
        ForeignKey("channels.xid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The external Discord ID of the channel this action targets",
    )
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="The game this action targets, and afterwards the game it resulted in",
    )
    kind = Column(
        String(20),
        nullable=False,
        doc="What this action asks the bot to do: create, join, or leave",
    )
    status = Column(
        String(20),
        nullable=False,
        default=WebActionStatus.PENDING.value,
        server_default=text(f"'{WebActionStatus.PENDING.value}'"),
        doc="Lifecycle status: pending, running, done, or error",
    )
    error_code = Column(
        String(50),
        nullable=True,
        doc="A stable code identifying why this action failed, when it did",
    )
    locale = Column(
        String(10),
        nullable=False,
        default="en",
        server_default=text("'en'"),
        doc="The locale negotiated for the web request that created this action",
    )
    params = cast(
        "dict[str, Any]",
        Column(
            JSONB,
            nullable=False,
            default=dict,
            server_default=text("'{}'::jsonb"),
            doc="JSON object describing the requested game settings",
        ),
    )
    notices = cast(
        "list[str]",
        Column(
            JSONB,
            nullable=False,
            default=list,
            server_default=text("'[]'::jsonb"),
            doc="Messages the bot would have replied with, for the website to show",
        ),
    )

    def to_data(self) -> WebActionData:
        from spellbot.data import WebActionData  # allow_inline

        return WebActionData(
            id=self.id,  # type: ignore
            created_at=self.created_at,  # type: ignore
            updated_at=self.updated_at,  # type: ignore
            resolved_at=self.resolved_at,  # type: ignore
            user_xid=self.user_xid,  # type: ignore
            guild_xid=self.guild_xid,  # type: ignore
            channel_xid=self.channel_xid,  # type: ignore
            game_id=self.game_id,  # type: ignore
            kind=self.kind,  # type: ignore
            status=self.status,  # type: ignore
            error_code=self.error_code,  # type: ignore
            locale=self.locale,  # type: ignore
            params=dict(self.params or {}),
            notices=list(self.notices or []),
        )
