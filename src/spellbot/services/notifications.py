from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from asgiref.sync import sync_to_async
from sqlalchemy import update
from sqlalchemy.sql.expression import and_

from spellbot.database import DatabaseSession
from spellbot.models import Notification


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
    deleted_at: datetime | None = None
    role: str | None = None

    # These are None if not yet persisted to the database:
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # These are None if not yet sent to Discord:
    message: int | None = None

    @staticmethod
    def from_db(obj: Notification) -> NotificationData:
        return NotificationData(
            link=obj.link,
            guild=obj.guild,
            channel=obj.channel,
            players=obj.players,
            format=obj.format,
            bracket=obj.bracket,
            service=obj.service,
            started_at=obj.started_at,
            deleted_at=obj.deleted_at,
            id=obj.id,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            message=obj.message,
        )


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

    @sync_to_async()
    def update(
        self,
        pk: int,
        players: list[str],
        started_at: datetime | None = None,
    ) -> NotificationData | None:
        obj = DatabaseSession.get(Notification, pk)
        if obj is None:
            return None
        if obj.deleted_at is not None:
            return None
        obj.players = players
        obj.started_at = started_at
        DatabaseSession.commit()
        DatabaseSession.refresh(obj)
        return obj.to_data()

    @sync_to_async()
    def set_message(self, pk: int, message: int) -> None:
        qs = (
            update(Notification.__table__)
            .where(and_(Notification.id == pk, Notification.deleted_at.is_(None)))
            .values(message=message)
        )
        DatabaseSession.execute(qs)
        DatabaseSession.commit()

    @sync_to_async()
    def delete(self, pk: int) -> NotificationData | None:
        obj = DatabaseSession.get(Notification, pk)
        if obj is None:
            return None
        if obj.deleted_at is not None:
            return None
        obj.deleted_at = datetime.now(tz=UTC)
        DatabaseSession.commit()
        DatabaseSession.refresh(obj)
        return obj.to_data()
