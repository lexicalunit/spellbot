from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.data import AlertData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelAlert:
    def test_alert_to_data(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        alert = factories.alert.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            preferences={"formats": [1, 4], "brackets": [2], "channels": [100, 200]},
        )

        alert_data = alert.to_data()
        assert isinstance(alert_data, AlertData)
        assert asdict(alert_data) == {
            "id": alert.id,
            "created_at": alert.created_at,
            "updated_at": alert.updated_at,
            "guild_xid": alert.guild_xid,
            "user_xid": alert.user_xid,
            "formats": [1, 4],
            "brackets": [2],
            "channels": [100, 200],
            "active_hours": None,
            "deleted_at": None,
        }

    def test_alert_to_data_empty_preferences(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        alert = factories.alert.create(guild_xid=guild.xid, user_xid=user.xid)

        alert_data = alert.to_data()
        assert alert_data.formats == []
        assert alert_data.brackets == []
        assert alert_data.channels == []
        assert alert_data.active_hours is None
        assert alert_data.deleted_at is None

    def test_alert_to_data_includes_deleted_at(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        deleted_at = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
        alert = factories.alert.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            deleted_at=deleted_at,
        )

        alert_data = alert.to_data()
        assert alert_data.deleted_at == deleted_at

    def test_alert_to_data_with_active_hours(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        alert = factories.alert.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            preferences={
                "formats": [],
                "brackets": [],
                "channels": [],
                "active_hours": {"start": 17, "end": 22, "tz": "America/Los_Angeles"},
            },
        )

        alert_data = alert.to_data()
        assert alert_data.active_hours == {
            "start": 17,
            "end": 22,
            "tz": "America/Los_Angeles",
        }
