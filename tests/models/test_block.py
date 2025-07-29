from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


class TestModelBlock:
    def test_block(self, factories: Factories) -> None:
        user1 = factories.user.create()
        user2 = factories.user.create()
        block = factories.block.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        assert block.to_dict() == {
            "user_xid": user1.xid,
            "blocked_user_xid": user2.xid,
            "created_at": block.created_at,
            "updated_at": block.updated_at,
        }
