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


@pytest.mark.asyncio
class TestMarkNotified:
    async def test_sets_notified_at(self, game: Game) -> None:
        assert game.notified_at is None
        game_id = int(game.id)  # type: ignore[arg-type]

        await alerts.mark_notified(game_id)

        refreshed = await DatabaseSession.get(GameModel, game_id)
        assert refreshed is not None
        assert refreshed.notified_at is not None
