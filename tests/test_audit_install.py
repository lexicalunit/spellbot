from __future__ import annotations

import pytest
from sqlalchemy import text

from spellbot import audit
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Guild, web_editable_columns


class TestAuditedColumns:
    def test_audited_columns_are_web_editable_plus_primary_key(self) -> None:
        assert audit.audited_columns(Channel) == set(web_editable_columns(Channel)) | {"xid"}
        assert audit.audited_columns(Guild) == set(web_editable_columns(Guild)) | {"xid"}

    def test_excluded_columns_are_the_non_audited_rest(self) -> None:
        channel_excludes = set(audit.excluded_columns(Channel))
        assert {"created_at", "updated_at", "name", "guild_xid"} <= channel_excludes
        assert "default_seats" not in channel_excludes  # an audited setting

    def test_extra_audited_columns_can_include_non_editable_column(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # `promote` is owner-only (not web-editable); opting it in audits it.
        assert "promote" not in audit.audited_columns(Guild)
        monkeypatch.setitem(audit.EXTRA_AUDITED_COLUMNS, "guilds", {"promote"})
        assert "promote" in audit.audited_columns(Guild)
        assert "promote" not in audit.excluded_columns(Guild)


@pytest.mark.asyncio
@pytest.mark.use_db
class TestTriggersInstalled:
    async def test_audit_triggers_attached_to_audited_tables(self) -> None:
        rows = (
            await DatabaseSession.execute(
                text(
                    "SELECT tgrelid::regclass::text AS tbl, tgname FROM pg_trigger "
                    "WHERE tgname LIKE 'audit_trigger_%'",
                ),
            )
        ).all()
        installed = {(row.tbl, row.tgname) for row in rows}
        for table in ("channels", "guilds"):
            for verb in ("insert", "update", "delete"):
                assert (table, f"audit_trigger_{verb}") in installed
