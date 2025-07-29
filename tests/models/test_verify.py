from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelVerify:
    def test_verify(self, factories: Factories) -> None:
        user = factories.user.create()
        guild = factories.guild.create()
        verify = factories.verify.create(user_xid=user.xid, guild_xid=guild.xid, verified=True)

        assert verify.to_dict() == {
            "guild_xid": verify.guild_xid,
            "user_xid": verify.user_xid,
            "verified": verify.verified,
        }
