# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from spellbot.enums import GameFormat
from spellbot.models import GameStatus
from spellbot.services import plays

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestPlaysServiceRecords:
    """Tests for user_records and channel_records (direct invocation for coverage)."""

    async def test_user_records_missing_user(self) -> None:
        assert await plays.user_records(user_xid=99999) is None

    async def test_user_records_returns_rows(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=8101, name="ur-guild")
        channel = factories.channel.create(xid=8201, name="ur-channel", guild=guild)
        user = factories.user.create(xid=8301, name="ur-user")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9101)
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        result = await plays.user_records(user_xid=user.xid)
        assert result is not None
        rows, total = result
        assert total == 1
        assert len(rows) == 1
        assert rows[0]["channel"] == channel.xid
        assert "seats" in rows[0]
        assert "bracket" in rows[0]
        assert "locale" in rows[0]

    async def test_channel_records_missing_guild(self) -> None:
        assert await plays.channel_records(guild_xid=99998, channel_xid=1) is None

    async def test_channel_records_missing_channel(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=8102, name="cr-guild")
        assert await plays.channel_records(guild_xid=guild.xid, channel_xid=99997) is None

    async def test_channel_records_returns_rows(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=8103, name="cr-guild2")
        channel = factories.channel.create(xid=8203, name="cr-channel", guild=guild)
        user = factories.user.create(xid=8303, name="cr-user")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9103)
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        result = await plays.channel_records(guild_xid=guild.xid, channel_xid=channel.xid)
        assert result is not None
        rows, total = result
        assert total == 1
        assert len(rows) == 1
        assert rows[0]["channel"] == channel.xid
        assert rows[0]["service"]
        assert "seats" in rows[0]
        assert "bracket" in rows[0]
        assert "locale" in rows[0]


@pytest.mark.asyncio
class TestPlaysServiceStreamingExports:
    """Tests for the streaming export helpers and target-existence validators."""

    async def test_user_export_target_exists_missing(self) -> None:
        assert await plays.user_export_target_exists(user_xid=99000) is False

    async def test_user_export_target_exists_present(self, factories: Factories) -> None:
        user = factories.user.create(xid=8401, name="ux-user")
        assert await plays.user_export_target_exists(user_xid=user.xid) is True

    async def test_channel_export_target_exists_missing_guild(self) -> None:
        assert await plays.channel_export_target_exists(guild_xid=99001, channel_xid=1) is False

    async def test_channel_export_target_exists_missing_channel(
        self,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=8402, name="cx-guild")
        assert (
            await plays.channel_export_target_exists(guild_xid=guild.xid, channel_xid=99002)
            is False
        )

    async def test_channel_export_target_exists_present(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=8403, name="cx-guild2")
        channel = factories.channel.create(xid=8503, name="cx-channel", guild=guild)
        assert (
            await plays.channel_export_target_exists(guild_xid=guild.xid, channel_xid=channel.xid)
            is True
        )

    async def test_stream_user_records_no_plays(self) -> None:
        rows = [r async for r in plays.stream_user_records(user_xid=99003)]
        assert rows == []

    async def test_stream_user_records_yields_rows(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=8405, name="sx-guild2")
        channel = factories.channel.create(xid=8505, name="sx-channel", guild=guild)
        user = factories.user.create(xid=8605, name="sx-user")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9105)
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        rows = [r async for r in plays.stream_user_records(user_xid=user.xid)]
        assert len(rows) == 1
        assert rows[0]["channel"] == channel.xid
        assert rows[0]["guild_name"] == guild.name
        assert rows[0]["channel_name"] == channel.name
        assert "seats" in rows[0]
        assert "bracket" in rows[0]
        assert "locale" in rows[0]

    async def test_stream_channel_records_missing_guild(self) -> None:
        rows = [r async for r in plays.stream_channel_records(guild_xid=99004, channel_xid=1)]
        assert rows == []

    async def test_stream_channel_records_missing_channel(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=8406, name="sc-guild")
        rows = [
            r async for r in plays.stream_channel_records(guild_xid=guild.xid, channel_xid=99005)
        ]
        assert rows == []

    async def test_stream_channel_records_yields_rows(
        self,
        factories: Factories,
        freezer: FrozenDateTimeFactory,
    ) -> None:
        freezer.move_to(datetime(2020, 6, 15, 12, 0, tzinfo=UTC))
        now = datetime.now(tz=UTC)

        guild = factories.guild.create(xid=8407, name="sc-guild2")
        channel = factories.channel.create(xid=8507, name="sc-channel", guild=guild)
        user = factories.user.create(xid=8607, name="sc-user")
        game = factories.game.create(
            guild=guild,
            channel=channel,
            status=GameStatus.STARTED.value,
            format=GameFormat.COMMANDER.value,
            started_at=now,
            created_at=now - timedelta(minutes=5),
        )
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9107)
        factories.play.create(game_id=game.id, user_xid=user.xid, og_guild_xid=guild.xid)

        rows = [
            r
            async for r in plays.stream_channel_records(
                guild_xid=guild.xid,
                channel_xid=channel.xid,
            )
        ]
        assert len(rows) == 1
        assert rows[0]["channel"] == channel.xid
        assert rows[0]["guild_name"] == guild.name
        assert rows[0]["channel_name"] == channel.name
        assert rows[0]["user_xid"] == str(user.xid)


class TestRulesHelpers:
    """Tests for normalize_rule and extract_ngrams helper functions."""

    def test_normalize_rule_strips_punctuation(self) -> None:
        assert plays.normalize_rule("no proxies!") == "no proxies"
        assert plays.normalize_rule("proxies ok...") == "proxies ok"
        assert plays.normalize_rule("rule?!") == "rule"

    def test_normalize_rule_empty_after_strip(self) -> None:
        # Edge case: rule becomes empty after stripping punctuation
        assert plays.normalize_rule("...") == ""
        assert plays.normalize_rule("!?") == ""

    def test_extract_ngrams_short_text(self) -> None:
        # Single word can't produce bigrams
        assert plays.extract_ngrams("proxies", 2) == []
        assert plays.extract_ngrams("no", 3) == []

    def test_extract_ngrams_produces_bigrams(self) -> None:
        result = plays.extract_ngrams("no proxies allowed", 2)
        assert "no proxies" in result
        assert "proxies allowed" in result

    def test_extract_ngrams_produces_trigrams(self) -> None:
        result = plays.extract_ngrams("no proxies allowed here", 3)
        assert "no proxies allowed" in result
        assert "proxies allowed here" in result
