from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spellbot.services import NotificationData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelNotification:
    def test_notification(self, factories: Factories) -> None:
        notif = factories.notification.create()

        assert notif.to_dict() == {
            "id": notif.id,
            "created_at": notif.created_at,
            "updated_at": notif.updated_at,
            "started_at": notif.started_at,
            "deleted_at": notif.deleted_at,
            "guild": notif.guild,
            "channel": notif.channel,
            "message": notif.message,
            "players": notif.players,
            "format": notif.format,
            "bracket": notif.bracket,
            "service": notif.service,
            "link": notif.link,
        }

    def test_notification_to_data(self, factories: Factories) -> None:
        notif = factories.notification.create()

        assert notif.to_data() == NotificationData(
            link=notif.link,
            guild=notif.guild,
            channel=notif.channel,
            players=notif.players,
            format=notif.format,
            bracket=notif.bracket,
            service=notif.service,
            started_at=notif.started_at,
            deleted_at=notif.deleted_at,
            id=notif.id,
            created_at=notif.created_at,
            updated_at=notif.updated_at,
            message=notif.message,
        )
