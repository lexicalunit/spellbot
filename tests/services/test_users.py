from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.models import Block, Game, Guild, Queue, User, Watch
from spellbot.services import UsersService
from tests.factories import UserFactory

if TYPE_CHECKING:
    from tests.fixtures import Factories

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

    async def test_users_get(self) -> None:
        users = UsersService()
        assert await users.get(201) is None

        UserFactory.create(xid=201)

        DatabaseSession.expire_all()
        user_data = await users.get(201)
        assert user_data is not None
        assert user_data.xid == 201

    async def test_users_is_banned(self) -> None:
        user1 = UserFactory.create(banned=False)
        user2 = UserFactory.create(banned=True)

        users = UsersService()
        user1_data = await users.get(user1.xid)
        user2_data = await users.get(user2.xid)
        assert user1_data is not None
        assert user2_data is not None
        assert not user1_data.banned
        assert user2_data.banned

    async def test_users_set_banned(self) -> None:
        user = UserFactory.create(banned=False)

        users = UsersService()
        updated = await users.set_banned(user.xid, banned=True)
        assert updated.banned

    async def test_users_current_game_id(self, game: Game) -> None:
        user = UserFactory.create(game=game)

        users = UsersService()
        user_data = await users.get(user.xid)
        assert user_data is not None
        assert await users.current_game_id(user_data, game.channel_xid) == game.id

    async def test_users_is_waiting(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        users = UsersService()
        user1_data = await users.get(user1.xid)
        assert user1_data is not None
        result = await users.is_waiting(user1_data, game.channel_xid)
        assert result is not None
        assert result.id == game.id

        user2_data = await users.get(user2.xid)
        assert user2_data is not None
        assert await users.is_waiting(user2_data, game.channel_xid) is None

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

        user1_data = await users.get(user1.xid)
        assert user1_data is not None
        await users.leave_game(user1_data, game.channel_xid)

        user2_data = await users.get(user2.xid)
        assert user2_data is not None
        await users.leave_game(user2_data, game.channel_xid)

        assert DatabaseSession.query(Queue).count() == 0

    async def test_users_current_game_id_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)

        users = UsersService()
        user_data = await users.get(user.xid)
        assert user_data is not None
        assert await users.current_game_id(user_data, channel.xid) is None

    async def test_users_is_waiting_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)

        users = UsersService()
        user_data = await users.get(user.xid)
        assert user_data is not None
        assert await users.is_waiting(user_data, channel.xid) is None

    async def test_users_leave_game_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)

        users = UsersService()
        user_data = await users.get(user.xid)
        assert user_data is not None

        # Queue entry still exists (game was soft-deleted but queue wasn't cleaned up)
        assert DatabaseSession.query(Queue).count() == 1

        # leave_game should not find the deleted game, so queue should remain
        await users.leave_game(user_data, channel.xid)

        # Queue entry should still exist since the game was deleted
        assert DatabaseSession.query(Queue).count() == 1
