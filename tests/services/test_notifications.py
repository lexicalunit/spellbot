from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async

from spellbot.database import DatabaseSession
from spellbot.models import Notification
from spellbot.services import NotificationData, NotificationsService

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceNotifications:
    async def test_create(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link",
            guild=101,
            channel=102,
            players=["a", "b", "c"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None
        assert data.created_at is not None
        assert data.updated_at is not None

    async def test_update(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link",
            guild=101,
            channel=102,
            players=["a", "b"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None

        updated = await notifs.update(data.id, ["a", "b", "c", "d"], datetime.now(tz=UTC))
        assert updated is not None
        assert updated.players == ["a", "b", "c", "d"]
        assert updated.started_at is not None

    async def test_update_not_found(self) -> None:
        notifs = NotificationsService()
        updated = await notifs.update(999999, ["a", "b"], None)
        assert updated is None

    async def test_update_already_deleted(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link",
            guild=101,
            channel=102,
            players=["a", "b"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None

        # Delete the notification first
        await notifs.delete(data.id)

        # Now try to update - should return None
        updated = await notifs.update(data.id, ["a", "b", "c"], None)
        assert updated is None

    async def test_set_message(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link",
            guild=101,
            channel=102,
            players=["a", "b"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None

        await notifs.set_message(data.id, 12345678)
        # The method doesn't return anything, but we can verify no error

    async def test_delete(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link",
            guild=101,
            channel=102,
            players=["a", "b"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None

        deleted = await notifs.delete(data.id)
        assert deleted is not None
        assert deleted.deleted_at is not None

    async def test_delete_not_found(self) -> None:
        notifs = NotificationsService()
        deleted = await notifs.delete(999999)
        assert deleted is None

    async def test_delete_already_deleted(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link",
            guild=101,
            channel=102,
            players=["a", "b"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None

        # Delete once
        await notifs.delete(data.id)

        # Try to delete again - should return None
        deleted = await notifs.delete(data.id)
        assert deleted is None

    async def test_inactive_notifications_empty(self) -> None:
        notifs = NotificationsService()
        inactive = await notifs.inactive_notifications()
        # We're not checking a specific count since other tests may have created data
        assert isinstance(inactive, list)

    async def test_inactive_notifications_with_expired(self) -> None:
        notifs = NotificationsService()
        data = NotificationData(
            link="http://link-expired",
            guild=201,
            channel=202,
            players=["x", "y"],
            format=1,
            bracket=2,
            service=3,
        )
        data = await notifs.create(data)
        assert data.id is not None

        @sync_to_async()
        def backdate_created_at(pk: int) -> None:
            obj = DatabaseSession.get(Notification, pk)
            # Set created_at to 1 hour ago so it appears expired
            obj.created_at = datetime.now(tz=UTC) - timedelta(hours=1)
            DatabaseSession.commit()

        await backdate_created_at(data.id)

        # Mock the settings with a short expire time
        with patch("spellbot.services.notifications.settings") as mock_settings:
            mock_settings.EXPIRE_TIME_M = 30  # 30 minutes - our notification is 1 hour old
            inactive = await notifs.inactive_notifications()
            # Should include our notification since it's not started, not deleted, and old
            links = [n["link"] for n in inactive]
            assert "http://link-expired" in links
