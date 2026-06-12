from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from spellbot import audit
from spellbot.services import channels
from spellbot.web.api import audit as audit_web

if TYPE_CHECKING:
    from aiohttp.client import ClientSession
    from pytest_mock import MockerFixture

    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestAuditDisplayHelpers:
    def test_field_label(self) -> None:
        assert audit_web.field_label("motd") == "MOTD"
        assert audit_web.field_label("default_seats") == "Default seats"

    def test_format_value(self) -> None:
        assert audit_web.format_value("default_format", 1) == "Commander"
        assert audit_web.format_value("default_format", 999) == "999"  # unknown enum value
        assert audit_web.format_value("blind_games", True) == "Enabled"
        assert audit_web.format_value("blind_games", False) == "Disabled"
        assert audit_web.format_value("motd", "") == "(empty)"
        assert audit_web.format_value("motd", None) == "(empty)"
        assert audit_web.format_value("voice_category", "Cat") == "Cat"

    def test_change_rows_actor_fallbacks(self) -> None:
        event = {
            "issued_at": datetime(2020, 1, 1, tzinfo=UTC),
            "actor_id": None,
            "actor_name": None,
            "source": None,
            "old_data": {"default_seats": 4},
            "changed_data": {"default_seats": 2},
        }
        row = audit_web._change_rows([event])[0]
        assert row["who"] == "—"
        assert row["source"] == "—"
        assert row["old"] == "4"
        assert row["new"] == "2"

    def test_change_rows_actor_id_without_name(self) -> None:
        event = {
            "issued_at": datetime(2020, 1, 1, tzinfo=UTC),
            "actor_id": 7,
            "actor_name": None,
            "source": "discord",
            "old_data": {},
            "changed_data": {"motd": "hi"},
        }
        assert audit_web._change_rows([event])[0]["who"] == "7"


async def _record_channel_change(channel_xid: int, **values: object) -> None:
    with audit.actor(42, "owner", audit.SOURCE_WEB):
        await channels.update_settings(channel_xid, **values)


@pytest.mark.asyncio
class TestAuditPageAccess:
    async def test_anonymous_is_redirected_to_login(
        self,
        client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await client.get(f"/g/{guild.xid}/audit", allow_redirects=False)
        assert resp.status == 302
        assert "/queues/login" in resp.headers["Location"]

    async def test_logged_in_non_moderator_forbidden(
        self,
        owner_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        resp = await owner_client.get(f"/g/{guild.xid}/audit")
        assert resp.status == 403

    async def test_non_integer_ids_are_404(self, mod_client: ClientSession) -> None:
        assert (await mod_client.get("/g/abc/audit")).status == 404
        assert (await mod_client.get("/g/1/c/xyz/audit")).status == 404

    async def test_invalid_page_defaults_to_first(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=207, name="guild")
        resp = await mod_client.get(f"/g/{guild.xid}/audit?page=notanumber")
        assert resp.status == 200


@pytest.mark.asyncio
class TestChannelAuditPage:
    async def test_shows_attributed_change(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=201, name="guild")
        channel = factories.channel.create(xid=301, name="channel", guild=guild, default_seats=4)

        resp = await mod_client.post(
            f"/g/{guild.xid}/c/{channel.xid}/settings",
            data={"default_seats": "2"},
            allow_redirects=False,
        )
        assert resp.status == 302

        resp = await mod_client.get(f"/g/{guild.xid}/c/{channel.xid}/audit")
        assert resp.status == 200
        text = await resp.text()
        assert "Default seats" in text
        assert "owner" in text  # actor name
        assert "web" in text  # source
        assert ">4<" in text  # old value
        assert ">2<" in text  # new value

    async def test_empty_when_no_changes(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=202, name="guild")
        channel = factories.channel.create(xid=302, name="channel", guild=guild)
        resp = await mod_client.get(f"/g/{guild.xid}/c/{channel.xid}/audit")
        assert resp.status == 200
        assert "No settings changes have been recorded yet." in await resp.text()

    async def test_history_link_on_settings_page(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=203, name="guild")
        channel = factories.channel.create(xid=303, name="channel", guild=guild)
        resp = await mod_client.get(f"/g/{guild.xid}/c/{channel.xid}")
        assert f"/g/{guild.xid}/c/{channel.xid}/audit" in await resp.text()

    async def test_pagination(
        self,
        mod_client: ClientSession,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        guild = factories.guild.create(xid=204, name="guild")
        channel = factories.channel.create(xid=304, name="channel", guild=guild, blind_games=False)
        # Toggle a boolean back and forth to record more than one page of changes.
        for i in range(audit.SETTINGS_CHANGE_PAGE_SIZE + 1):
            await _record_channel_change(channel.xid, blind_games=bool(i % 2 == 0))

        first = await mod_client.get(f"/g/{guild.xid}/c/{channel.xid}/audit")
        assert "Next page" in await first.text()
        second = await mod_client.get(f"/g/{guild.xid}/c/{channel.xid}/audit?page=1")
        assert "Previous page" in await second.text()


@pytest.mark.asyncio
class TestGuildAuditPage:
    async def test_shows_attributed_change(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=205, name="guild", motd="old")

        resp = await mod_client.post(
            f"/g/{guild.xid}/settings",
            data={"motd": "new motd"},
            allow_redirects=False,
        )
        assert resp.status == 302

        resp = await mod_client.get(f"/g/{guild.xid}/audit")
        assert resp.status == 200
        text = await resp.text()
        assert "MOTD" in text
        assert "new motd" in text
        assert "owner" in text

    async def test_history_link_on_settings_page(
        self,
        mod_client: ClientSession,
        factories: Factories,
    ) -> None:
        guild = factories.guild.create(xid=206, name="guild")
        resp = await mod_client.get(f"/g/{guild.xid}")
        assert f"/g/{guild.xid}/audit" in await resp.text()
