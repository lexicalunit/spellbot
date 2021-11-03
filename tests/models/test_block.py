from tests.factories.block import BlockFactory
from tests.factories.user import UserFactory


class TestModelBlock:
    def test_block(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        block = BlockFactory.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        assert block.to_dict() == {
            "user_xid": user1.xid,
            "blocked_user_xid": user2.xid,
        }
