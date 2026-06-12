from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import select

from spellbot import audit
from spellbot.audit import Activity, Transaction
from spellbot.database import DatabaseSession
from spellbot.services import channels, guilds

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


async def make_changes(table_name: str) -> list[dict[str, Any]]:
    rows = (
        await DatabaseSession.execute(
            select(
                Activity.verb,
                Activity.old_data,
                Activity.changed_data,
                Transaction.actor_id,
                Transaction.actor_name,
                Transaction.source,
            )
            .join(Transaction, Activity.transaction_id == Transaction.id, isouter=True)
            .where(Activity.table_name == table_name, Activity.verb == "update")
            .order_by(Activity.id),
        )
    ).all()
    return [dict(r._mapping) for r in rows]


@pytest.mark.asyncio
class TestSettingsAudit:
    async def test_channel_change_is_attributed(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=1)
        channel = factories.channel.create(xid=2, guild=guild, default_seats=4)

        with audit.actor(123, "Amy", audit.SOURCE_WEB):
            await channels.update_settings(channel.xid, default_seats=2)

        changes = await make_changes("channels")
        assert len(changes) == 1
        row = changes[0]
        assert row["changed_data"] == {"default_seats": 2}
        assert row["old_data"]["default_seats"] == 4
        assert row["actor_id"] == 123
        assert row["actor_name"] == "Amy"
        assert row["source"] == "web"

    async def test_noop_change_records_nothing(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=1)
        channel = factories.channel.create(xid=2, guild=guild, default_seats=4)

        with audit.actor(123, "Amy", audit.SOURCE_WEB):
            await channels.update_settings(channel.xid, default_seats=4)  # same value

        assert await make_changes("channels") == []

    async def test_unattributed_change_when_no_actor(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=1)
        channel = factories.channel.create(xid=2, guild=guild, blind_games=False)

        await channels.update_settings(channel.xid, blind_games=True)  # no actor context

        changes = await make_changes("channels")
        assert len(changes) == 1
        assert changes[0]["changed_data"] == {"blind_games": True}
        assert changes[0]["actor_id"] is None
        assert changes[0]["source"] is None

    async def test_guild_change_is_attributed(self, factories: Factories) -> None:
        guild = factories.guild.create(xid=1, motd="old")

        with audit.actor(999, "Mod", audit.SOURCE_DISCORD):
            await guilds.update_settings(guild.xid, motd="new")

        changes = await make_changes("guilds")
        assert len(changes) == 1
        assert changes[0]["changed_data"] == {"motd": "new"}
        assert changes[0]["actor_id"] == 999
        assert changes[0]["source"] == "discord"
