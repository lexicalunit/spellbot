from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from spellbot.data import VerifyData

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelVerify:
    def test_verify_to_data(self, factories: Factories) -> None:
        user = factories.user.create()
        guild = factories.guild.create()
        verify = factories.verify.create(user_xid=user.xid, guild_xid=guild.xid, verified=True)

        verify_data = verify.to_data()
        assert isinstance(verify_data, VerifyData)
        assert asdict(verify_data) == {
            "guild_xid": verify.guild_xid,
            "user_xid": verify.user_xid,
            "verified": verify.verified,
        }
