from tests.fixtures import Factories


class TestModelBlock:
    def test_block(self, factories: Factories):
        user1 = factories.user.create()
        user2 = factories.user.create()
        block = factories.block.create(user_xid=user1.xid, blocked_user_xid=user2.xid)

        assert block.to_dict() == {
            "user_xid": user1.xid,
            "blocked_user_xid": user2.xid,
        }
