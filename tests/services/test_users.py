from unittest.mock import MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import Block, User, Watch
from spellbot.services.users import UsersService
from tests.factories import UserFactory


@pytest.mark.asyncio
class TestServiceUsers:
    async def test_users_upsert(self):
        user = UserFactory.create(xid=201)

        discord_user = MagicMock()
        discord_user.id = 201
        discord_user.display_name = "user-name"

        users = UsersService()
        await users.upsert(discord_user)

        DatabaseSession.expire_all()
        user = DatabaseSession.query(User).get(discord_user.id)
        assert user and user.xid == discord_user.id
        assert user.name == "user-name"

        discord_user.display_name = "new-name"
        await users.upsert(discord_user)

        DatabaseSession.expire_all()
        user = DatabaseSession.query(User).get(discord_user.id)
        assert user and user.xid == discord_user.id
        assert user.name == "new-name"

    async def test_users_select(self):
        users = UsersService()
        assert not await users.select(201)

        UserFactory.create(xid=201)

        DatabaseSession.expire_all()
        assert await users.select(201)

    async def test_users_is_banned(self):
        user1 = UserFactory.create(banned=False)
        user2 = UserFactory.create(banned=True)

        users = UsersService()
        assert not await users.is_banned(user1.xid)
        assert await users.is_banned(user2.xid)

        users = UsersService()
        await users.select(user1.xid)
        assert not await users.is_banned()

        users = UsersService()
        await users.select(user2.xid)
        assert await users.is_banned()

    async def test_users_set_banned(self):
        user = UserFactory.create(banned=False)

        users = UsersService()
        await users.set_banned(True, user.xid)
        assert await users.is_banned(user.xid)

    async def test_users_current_game_id(self, game):
        user = UserFactory.create(game=game)

        users = UsersService()
        await users.select(user.xid)
        assert await users.current_game_id() == game.id

    async def test_users_leave_game(self, game):
        user = UserFactory.create(game=game)

        users = UsersService()
        await users.select(user.xid)
        await users.leave_game()
        assert await users.current_game_id() is None

    async def test_users_is_waiting(self, game):
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        users = UsersService()
        await users.select(user1.xid)
        assert await users.is_waiting()
        await users.select(user2.xid)
        assert not await users.is_waiting()

    async def test_users_block(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()

        users = UsersService()
        await users.block(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        blocks = [b.to_dict() for b in DatabaseSession.query(Block).all()]
        assert blocks == [{"user_xid": user1.xid, "blocked_user_xid": user2.xid}]

    async def test_users_unblock(self):
        user1 = UserFactory.create()
        user2 = UserFactory.create()

        users = UsersService()
        await users.block(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        blocks = [b.to_dict() for b in DatabaseSession.query(Block).all()]
        assert blocks == [{"user_xid": user1.xid, "blocked_user_xid": user2.xid}]

        await users.unblock(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        blocks = [b.to_dict() for b in DatabaseSession.query(Block).all()]
        assert blocks == []

    async def test_users_watch(self, guild):
        user = UserFactory.create()

        users = UsersService()
        await users.watch(guild_xid=guild.xid, user_xid=user.xid, note="note")

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == [{"guild_xid": guild.xid, "user_xid": user.xid, "note": "note"}]

    async def test_users_watch_upsert(self, guild):
        user = UserFactory.create()

        users = UsersService()
        await users.watch(guild_xid=guild.xid, user_xid=user.xid, note="note1")
        await users.watch(guild_xid=guild.xid, user_xid=user.xid, note="note2")

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == [
            {
                "guild_xid": guild.xid,
                "user_xid": user.xid,
                "note": "note2",
            },
        ]

    async def test_users_watch_without_note(self, guild):
        user = UserFactory.create()

        users = UsersService()
        await users.watch(guild_xid=guild.xid, user_xid=user.xid)

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == [{"guild_xid": guild.xid, "user_xid": user.xid, "note": None}]

    async def test_users_unwatch(self, guild):
        user = UserFactory.create()

        users = UsersService()
        await users.watch(guild_xid=guild.xid, user_xid=user.xid, note="note")

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == [{"guild_xid": guild.xid, "user_xid": user.xid, "note": "note"}]

        await users.unwatch(guild_xid=guild.xid, user_xid=user.xid)

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == []
