from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession
from spellbot.models import Notification

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class NotificationData:
    link: str
    guild: int
    channel: int
    players: list[str]
    format: int
    bracket: int
    service: int
    started_at: datetime | None = None

    # These are None if not yet persisted to the database:
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationsService:
    @sync_to_async()
    def create(self, notif: NotificationData) -> NotificationData:
        db_object = Notification(
            link=notif.link,
            guild=notif.guild,
            channel=notif.channel,
            players=notif.players,
            format=notif.format,
            bracket=notif.bracket,
            service=notif.service,
            started_at=notif.started_at,
        )
        DatabaseSession.add(db_object)
        DatabaseSession.commit()
        DatabaseSession.refresh(db_object)
        notif.id = db_object.id
        notif.created_at = db_object.created_at
        notif.updated_at = db_object.updated_at
        return notif
