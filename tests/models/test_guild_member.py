from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelGuildMember:
    def test_guild_member(self, factories: Factories) -> None:
        guild = factories.guild.create()
        user = factories.user.create()
        guild_member = factories.guild_member.create(
            user_xid=user.xid,
            guild_xid=guild.xid,
        )

        assert guild_member.to_dict() == {
            "user_xid": user.xid,
            "guild_xid": guild.xid,
            "created_at": guild_member.created_at,
            "updated_at": guild_member.updated_at,
        }
