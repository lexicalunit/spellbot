from spellbot.database import DatabaseSession
from spellbot.models.block import Block
from spellbot.models.user import User


class TestModelBlock:
    def test_block(self):
        user1 = User(xid=201, name="user1")
        user2 = User(xid=202, name="user2")
        DatabaseSession.add_all([user1, user2])
        DatabaseSession.commit()

        block = Block(user_xid=user1.xid, blocked_user_xid=user2.xid)
        DatabaseSession.add(block)
        DatabaseSession.commit()

        assert block.to_dict() == {
            "user_xid": user1.xid,
            "blocked_user_xid": user2.xid,
        }
