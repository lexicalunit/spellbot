from __future__ import annotations

import pytest

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
