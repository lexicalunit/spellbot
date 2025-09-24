from __future__ import annotations

from unittest.mock import ANY, MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import Block, Game, Guild, Queue, User, Watch
from spellbot.services import UsersService
from tests.factories import UserFactory

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceUsers:
    async def test_users_upsert(self) -> None:
        user = UserFactory.create(xid=201)

        discord_user = MagicMock()
        discord_user.id = 201
        discord_user.display_name = "user-name"

        users = UsersService()
        await users.upsert(discord_user)

        DatabaseSession.expire_all()
        user = DatabaseSession.get(User, discord_user.id)
        assert user
        assert user.xid == discord_user.id
        assert user.name == "user-name"

        discord_user.display_name = "new-name"
        await users.upsert(discord_user)

        DatabaseSession.expire_all()
        user = DatabaseSession.get(User, discord_user.id)
        assert user
        assert user.xid == discord_user.id
        assert user.name == "new-name"

    async def test_users_select(self) -> None:
        users = UsersService()
        assert not await users.select(201)

        UserFactory.create(xid=201)

        DatabaseSession.expire_all()
        assert await users.select(201)

    async def test_users_is_banned(self) -> None:
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

    async def test_users_set_banned(self) -> None:
        user = UserFactory.create(banned=False)

        users = UsersService()
        await users.set_banned(True, user.xid)
        assert await users.is_banned(user.xid)

    async def test_users_current_game_id(self, game: Game) -> None:
        user = UserFactory.create(game=game)

        users = UsersService()
        await users.select(user.xid)
        assert await users.current_game_id(game.channel_xid) == game.id

    async def test_users_is_waiting(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        users = UsersService()
        await users.select(user1.xid)
        assert await users.is_waiting(game.channel_xid)
        await users.select(user2.xid)
        assert not await users.is_waiting(game.channel_xid)

    async def test_users_block(self) -> None:
        user1 = UserFactory.create()
        user2 = UserFactory.create()

        users = UsersService()
        await users.block(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        blocks = [b.to_dict() for b in DatabaseSession.query(Block).all()]
        assert blocks == [
            {
                "user_xid": user1.xid,
                "blocked_user_xid": user2.xid,
                "created_at": ANY,
                "updated_at": ANY,
            },
        ]

    async def test_users_unblock(self) -> None:
        user1 = UserFactory.create()
        user2 = UserFactory.create()

        users = UsersService()
        await users.block(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        blocks = [b.to_dict() for b in DatabaseSession.query(Block).all()]
        assert blocks == [
            {
                "user_xid": user1.xid,
                "blocked_user_xid": user2.xid,
                "created_at": ANY,
                "updated_at": ANY,
            },
        ]

        await users.unblock(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        blocks = [b.to_dict() for b in DatabaseSession.query(Block).all()]
        assert blocks == []

    async def test_users_watch(self, guild: Guild) -> None:
        user = UserFactory.create()

        users = UsersService()
        await users.watch(guild_xid=guild.xid, user_xid=user.xid, note="note")

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == [{"guild_xid": guild.xid, "user_xid": user.xid, "note": "note"}]

    async def test_users_watch_upsert(self, guild: Guild) -> None:
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

    async def test_users_watch_without_note(self, guild: Guild) -> None:
        user = UserFactory.create()

        users = UsersService()
        await users.watch(guild_xid=guild.xid, user_xid=user.xid)

        DatabaseSession.expire_all()
        watches = [w.to_dict() for w in DatabaseSession.query(Watch).all()]
        assert watches == [{"guild_xid": guild.xid, "user_xid": user.xid, "note": None}]

    async def test_users_unwatch(self, guild: Guild) -> None:
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

    async def test_users_leave_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()
        users = UsersService()

        assert DatabaseSession.query(Queue).count() == 1

        await users.select(user1.xid)
        await users.leave_game(game.channel_xid)
        await users.select(user2.xid)
        await users.leave_game(game.channel_xid)

        assert DatabaseSession.query(Queue).count() == 0
