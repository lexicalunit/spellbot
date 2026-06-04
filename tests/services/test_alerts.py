from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot.data import AlertData
from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket, GameFormat
from spellbot.models import Game as GameModel
from spellbot.services import alerts

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from spellbot.models import Game, Guild
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceAlerts:
    async def test_upsert_inserts_new_record(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        result = await alerts.upsert(
            guild.xid,
            user.xid,
            formats=[1, 4],
            brackets=[2],
            channels=[111, 222],
        )

        assert isinstance(result, AlertData)
        assert result.guild_xid == guild.xid
        assert result.user_xid == user.xid
        assert result.formats == [1, 4]
        assert result.brackets == [2]
        assert result.channels == [111, 222]

    async def test_upsert_updates_existing_record(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        await alerts.upsert(guild.xid, user.xid, formats=[1], brackets=[3])

        updated = await alerts.upsert(
            guild.xid,
            user.xid,
            formats=[2, 5],
            brackets=[],
        )

        assert updated.formats == [2, 5]
        assert updated.brackets == []

        again = await alerts.get_for_user_guild(guild.xid, user.xid)
        assert again is not None
        assert again.id == updated.id
        assert again.formats == [2, 5]
        assert again.brackets == []

    async def test_upsert_deduplicates_and_sorts_values(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        result = await alerts.upsert(
            guild.xid,
            user.xid,
            formats=[4, 1, 1, 4],
            brackets=[3, 2, 2],
            channels=[999, 100, 100, 500],
        )

        assert result.formats == [1, 4]
        assert result.brackets == [2, 3]
        assert result.channels == [100, 500, 999]

    async def test_get_for_user_guild_returns_none_when_absent(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        assert await alerts.get_for_user_guild(guild.xid, user.xid) is None

    async def test_get_for_user_guild_returns_data_when_present(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=user.xid,
            preferences={"formats": [1], "brackets": [2], "channels": [42]},
        )

        result = await alerts.get_for_user_guild(guild.xid, user.xid)
        assert result is not None
        assert result.formats == [1]
        assert result.brackets == [2]
        assert result.channels == [42]

    async def test_delete_removes_existing_row(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        await alerts.upsert(guild.xid, user.xid, formats=[1])

        removed = await alerts.delete(guild.xid, user.xid)

        assert removed is True
        assert await alerts.get_for_user_guild(guild.xid, user.xid) is None

    async def test_delete_is_idempotent_when_absent(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        removed = await alerts.delete(guild.xid, user.xid)

        assert removed is False

    async def test_delete_only_removes_target_user(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        target = factories.user.create()
        bystander = factories.user.create()
        await alerts.upsert(guild.xid, target.xid, formats=[1])
        await alerts.upsert(guild.xid, bystander.xid, formats=[2])

        await alerts.delete(guild.xid, target.xid)

        assert await alerts.get_for_user_guild(guild.xid, target.xid) is None
        remaining = await alerts.get_for_user_guild(guild.xid, bystander.xid)
        assert remaining is not None
        assert remaining.formats == [2]

    async def test_delete_is_idempotent_for_already_deleted_row(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        await alerts.upsert(guild.xid, user.xid, formats=[1])
        assert await alerts.delete(guild.xid, user.xid) is True

        again = await alerts.delete(guild.xid, user.xid)

        assert again is False

    async def test_get_for_user_guild_excludes_soft_deleted_by_default(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        await alerts.upsert(guild.xid, user.xid, formats=[1])
        await alerts.delete(guild.xid, user.xid)

        assert await alerts.get_for_user_guild(guild.xid, user.xid) is None

    async def test_get_for_user_guild_returns_soft_deleted_when_included(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        await alerts.upsert(
            guild.xid,
            user.xid,
            formats=[1, 4],
            brackets=[2],
            channels=[42],
            active_hours={"start": 17, "end": 22, "tz": "UTC"},
        )
        await alerts.delete(guild.xid, user.xid)

        result = await alerts.get_for_user_guild(guild.xid, user.xid, include_deleted=True)

        assert result is not None
        assert result.deleted_at is not None
        assert result.formats == [1, 4]
        assert result.brackets == [2]
        assert result.channels == [42]
        assert result.active_hours == {"start": 17, "end": 22, "tz": "UTC"}

    async def test_get_for_user_guild_include_deleted_returns_active_row(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        await alerts.upsert(guild.xid, user.xid, formats=[1])

        result = await alerts.get_for_user_guild(guild.xid, user.xid, include_deleted=True)

        assert result is not None
        assert result.deleted_at is None
        assert result.formats == [1]

    async def test_upsert_restores_soft_deleted_record(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        original = await alerts.upsert(
            guild.xid,
            user.xid,
            formats=[1, 4],
            brackets=[2],
            channels=[42],
            active_hours={"start": 17, "end": 22, "tz": "UTC"},
        )
        await alerts.delete(guild.xid, user.xid)
        deleted = await alerts.get_for_user_guild(
            guild.xid,
            user.xid,
            include_deleted=True,
        )
        assert deleted is not None
        assert deleted.deleted_at is not None

        restored = await alerts.upsert(
            guild.xid,
            user.xid,
            formats=deleted.formats,
            brackets=deleted.brackets,
            channels=deleted.channels,
            active_hours=deleted.active_hours,
        )

        assert restored.id == original.id
        assert restored.deleted_at is None
        assert restored.formats == [1, 4]
        assert restored.brackets == [2]
        assert restored.channels == [42]
        assert restored.active_hours == {"start": 17, "end": 22, "tz": "UTC"}
        active = await alerts.get_for_user_guild(guild.xid, user.xid)
        assert active is not None
        assert active.id == original.id

    async def test_upsert_persists_active_hours(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        result = await alerts.upsert(
            guild.xid,
            user.xid,
            active_hours={"start": 17, "end": 22, "tz": "America/Los_Angeles"},
        )

        assert result.active_hours == {
            "start": 17,
            "end": 22,
            "tz": "America/Los_Angeles",
        }
        fetched = await alerts.get_for_user_guild(guild.xid, user.xid)
        assert fetched is not None
        assert fetched.active_hours == result.active_hours

    async def test_upsert_omits_active_hours_when_not_provided(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        result = await alerts.upsert(guild.xid, user.xid, formats=[1])

        assert result.active_hours is None

    async def test_upsert_raises_on_invalid_active_hours(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        with pytest.raises(ValueError, match="hours or less"):
            await alerts.upsert(
                guild.xid,
                user.xid,
                active_hours={"start": 1, "end": 10, "tz": "UTC"},
            )


@pytest.mark.asyncio
class TestGetGuildXidsForUser:
    async def test_returns_empty_set_when_user_has_no_alerts(
        self,
        factories: Factories,
    ) -> None:
        user = factories.user.create()

        assert await alerts.get_guild_xids_for_user(user.xid) == set()

    async def test_returns_only_guilds_with_alerts_for_user(
        self,
        factories: Factories,
    ) -> None:
        user = factories.user.create()
        other = factories.user.create()
        g1 = factories.guild.create()
        g2 = factories.guild.create()
        g3 = factories.guild.create()
        await alerts.upsert(g1.xid, user.xid, formats=[1])
        await alerts.upsert(g2.xid, user.xid, brackets=[2])
        await alerts.upsert(g3.xid, other.xid, formats=[1])

        result = await alerts.get_guild_xids_for_user(user.xid)

        assert result == {g1.xid, g2.xid}


@pytest.mark.asyncio
class TestFindMatchingUserXids:
    async def test_returns_users_with_matching_or_empty_preferences(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        wants_format = factories.user.create()
        wants_other_format = factories.user.create()
        wants_channel = factories.user.create()
        wants_other_channel = factories.user.create()
        wants_anything = factories.user.create()
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=wants_format.xid,
            preferences={"formats": [GameFormat.COMMANDER.value], "brackets": [], "channels": []},
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=wants_other_format.xid,
            preferences={
                "formats": [GameFormat.TWO_HEADED_GIANT.value],
                "brackets": [],
                "channels": [],
            },
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=wants_channel.xid,
            preferences={"formats": [], "brackets": [], "channels": [channel.xid]},
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=wants_other_channel.xid,
            preferences={"formats": [], "brackets": [], "channels": [channel.xid + 99]},
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=wants_anything.xid,
            preferences={"formats": [], "brackets": [], "channels": []},
        )

        result = await alerts.find_matching_user_xids(
            guild_xid=guild.xid,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            channel_xid=channel.xid,
        )

        assert set(result) == {wants_format.xid, wants_channel.xid, wants_anything.xid}

    async def test_excludes_banned_users(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        banned = factories.user.create(banned=True)
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=banned.xid,
            preferences={"formats": [], "brackets": [], "channels": []},
        )

        result = await alerts.find_matching_user_xids(
            guild_xid=guild.xid,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            channel_xid=channel.xid,
        )

        assert banned.xid not in result

    async def test_excludes_users_in_a_pending_game_in_any_guild(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        other_guild = factories.guild.create()
        other_channel = factories.channel.create(guild=other_guild)
        in_pending_other = factories.user.create()
        free = factories.user.create()
        for user in (in_pending_other, free):
            factories.alert.create(
                guild_xid=guild.xid,
                user_xid=user.xid,
                preferences={"formats": [], "brackets": [], "channels": []},
            )
        pending_game = factories.game.create(guild=other_guild, channel=other_channel)
        factories.queue.create(
            user_xid=in_pending_other.xid,
            game_id=pending_game.id,
            og_guild_xid=other_guild.xid,
        )

        result = await alerts.find_matching_user_xids(
            guild_xid=guild.xid,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            channel_xid=channel.xid,
        )

        assert in_pending_other.xid not in result
        assert free.xid in result

    async def test_does_not_exclude_users_in_started_or_deleted_games(
        self,
        guild: Guild,
        factories: Factories,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        in_started = factories.user.create()
        in_deleted = factories.user.create()
        for user in (in_started, in_deleted):
            factories.alert.create(
                guild_xid=guild.xid,
                user_xid=user.xid,
                preferences={"formats": [], "brackets": [], "channels": []},
            )
        started_game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime.now(tz=UTC),
        )
        deleted_game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime.now(tz=UTC),
        )
        factories.queue.create(
            user_xid=in_started.xid,
            game_id=started_game.id,
            og_guild_xid=guild.xid,
        )
        factories.queue.create(
            user_xid=in_deleted.xid,
            game_id=deleted_game.id,
            og_guild_xid=guild.xid,
        )

        result = await alerts.find_matching_user_xids(
            guild_xid=guild.xid,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            channel_xid=channel.xid,
        )

        assert {in_started.xid, in_deleted.xid}.issubset(set(result))

    async def test_filters_users_outside_active_hours(
        self,
        guild: Guild,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2024, 6, 1, 10, 0, tzinfo=UTC))
        channel = factories.channel.create(guild=guild)
        within = factories.user.create()
        outside = factories.user.create()
        wrap_within = factories.user.create()
        no_hours = factories.user.create()
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=within.xid,
            preferences={
                "formats": [],
                "brackets": [],
                "channels": [],
                "active_hours": {"start": 8, "end": 16, "tz": "UTC"},
            },
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=outside.xid,
            preferences={
                "formats": [],
                "brackets": [],
                "channels": [],
                "active_hours": {"start": 17, "end": 22, "tz": "UTC"},
            },
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=wrap_within.xid,
            preferences={
                "formats": [],
                "brackets": [],
                "channels": [],
                "active_hours": {"start": 22, "end": 12, "tz": "UTC"},
            },
        )
        factories.alert.create(
            guild_xid=guild.xid,
            user_xid=no_hours.xid,
            preferences={"formats": [], "brackets": [], "channels": []},
        )

        result = await alerts.find_matching_user_xids(
            guild_xid=guild.xid,
            format=GameFormat.COMMANDER.value,
            bracket=GameBracket.NONE.value,
            channel_xid=channel.xid,
        )

        assert set(result) == {within.xid, wrap_within.xid, no_hours.xid}


@pytest.mark.asyncio
class TestMarkNotified:
    async def test_sets_notified_at(self, game: Game) -> None:
        assert game.notified_at is None
        game_id = int(game.id)  # type: ignore[arg-type]

        await alerts.mark_notified(game_id)

        refreshed = await DatabaseSession.get(GameModel, game_id)
        assert refreshed is not None
        assert refreshed.notified_at is not None


class TestParseActiveHours:
    def test_returns_none_for_falsy(self) -> None:
        assert alerts.parse_active_hours(None) is None
        assert alerts.parse_active_hours({}) is None
        assert alerts.parse_active_hours("") is None

    def test_canonicalizes_valid_payload(self) -> None:
        result = alerts.parse_active_hours(
            {"start": "17", "end": "22", "tz": "America/Los_Angeles"},
        )
        assert result == {"start": 17, "end": 22, "tz": "America/Los_Angeles"}

    def test_allows_wrap_around_within_limit(self) -> None:
        result = alerts.parse_active_hours(
            {"start": 22, "end": 5, "tz": "UTC"},
        )
        assert result == {"start": 22, "end": 5, "tz": "UTC"}

    def test_rejects_non_object(self) -> None:
        with pytest.raises(ValueError, match="must be an object"):
            alerts.parse_active_hours("nope")

    def test_rejects_missing_fields(self) -> None:
        with pytest.raises(ValueError, match="requires integer"):
            alerts.parse_active_hours({"start": 1, "end": 2})

    def test_rejects_non_integer_hours(self) -> None:
        with pytest.raises(ValueError, match="requires integer"):
            alerts.parse_active_hours({"start": "x", "end": "y", "tz": "UTC"})

    def test_rejects_out_of_range_hours(self) -> None:
        with pytest.raises(ValueError, match="between 0 and 23"):
            alerts.parse_active_hours({"start": -1, "end": 5, "tz": "UTC"})
        with pytest.raises(ValueError, match="between 0 and 23"):
            alerts.parse_active_hours({"start": 0, "end": 24, "tz": "UTC"})

    def test_rejects_equal_start_and_end(self) -> None:
        with pytest.raises(ValueError, match="must differ"):
            alerts.parse_active_hours({"start": 9, "end": 9, "tz": "UTC"})

    def test_rejects_range_exceeding_max(self) -> None:
        with pytest.raises(ValueError, match="hours or less"):
            alerts.parse_active_hours({"start": 0, "end": 12, "tz": "UTC"})

    def test_rejects_invalid_timezone(self) -> None:
        with pytest.raises(ValueError, match="invalid timezone"):
            alerts.parse_active_hours({"start": 1, "end": 5, "tz": "Mars/Olympus"})


class TestIsWithinActiveHours:
    def test_returns_true_when_no_active_hours(self) -> None:
        now = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        assert alerts.is_within_active_hours(None, now) is True
        assert alerts.is_within_active_hours({}, now) is True

    def test_returns_true_for_malformed_payload(self) -> None:
        now = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        assert alerts.is_within_active_hours("not-a-dict", now) is True
        assert alerts.is_within_active_hours({"start": "x"}, now) is True
        assert (
            alerts.is_within_active_hours(
                {"start": 1, "end": 5, "tz": "Mars/Nope"},
                now,
            )
            is True
        )

    def test_returns_true_when_start_equals_end(self) -> None:
        now = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 5, "end": 5, "tz": "UTC"},
                now,
            )
            is True
        )

    def test_inside_normal_window(self) -> None:
        now = datetime(2024, 6, 1, 18, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 17, "end": 22, "tz": "UTC"},
                now,
            )
            is True
        )

    def test_outside_normal_window(self) -> None:
        now = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 17, "end": 22, "tz": "UTC"},
                now,
            )
            is False
        )

    def test_inside_wrap_around_late_evening(self) -> None:
        now = datetime(2024, 6, 1, 23, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 22, "end": 3, "tz": "UTC"},
                now,
            )
            is True
        )

    def test_inside_wrap_around_early_morning(self) -> None:
        now = datetime(2024, 6, 1, 2, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 22, "end": 3, "tz": "UTC"},
                now,
            )
            is True
        )

    def test_outside_wrap_around(self) -> None:
        now = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 22, "end": 3, "tz": "UTC"},
                now,
            )
            is False
        )

    def test_uses_target_timezone(self) -> None:
        now = datetime(2024, 6, 1, 4, 0, tzinfo=UTC)
        assert (
            alerts.is_within_active_hours(
                {"start": 17, "end": 22, "tz": "America/Los_Angeles"},
                now,
            )
            is True
        )
        assert (
            alerts.is_within_active_hours(
                {"start": 17, "end": 22, "tz": "UTC"},
                now,
            )
            is False
        )
