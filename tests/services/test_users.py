# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
import pytest
from sqlalchemy import func, select

from spellbot.database import DatabaseSession
from spellbot.models import Block, Game, Play, Queue, User, UserAward
from spellbot.services import users
from spellbot.settings import settings
from tests.factories import UserFactory

if TYPE_CHECKING:
    from decoy import Decoy

    from tests.fixtures import Factories, Stub

pytestmark = pytest.mark.use_db


@pytest.mark.asyncio
class TestServiceUsers:
    async def test_users_upsert(self, decoy: Decoy) -> None:
        user = UserFactory.create(xid=201)

        discord_user = decoy.mock(cls=discord.User)
        discord_user.id = 201
        decoy.when(discord_user.display_name).then_return("user-name")

        await users.upsert(discord_user)

        DatabaseSession.expire_all()
        user = await DatabaseSession.get(User, discord_user.id)
        assert user
        assert user.xid == discord_user.id
        assert user.name == "user-name"

        decoy.when(discord_user.display_name).then_return("new-name")
        await users.upsert(discord_user)

        DatabaseSession.expire_all()
        user = await DatabaseSession.get(User, discord_user.id)
        assert user
        assert user.xid == discord_user.id
        assert user.name == "new-name"

    async def test_users_get(self) -> None:
        assert await users.get(201) is None

        UserFactory.create(xid=201)

        DatabaseSession.expire_all()
        user_data = await users.get(201)
        assert user_data is not None
        assert user_data.xid == 201

    async def test_users_is_banned(self) -> None:
        user1 = UserFactory.create(banned=False)
        user2 = UserFactory.create(banned=True)

        user1_data = await users.get(user1.xid)
        user2_data = await users.get(user2.xid)
        assert user1_data is not None
        assert user2_data is not None
        assert not user1_data.banned
        assert user2_data.banned

    async def test_users_set_banned(self) -> None:
        user = UserFactory.create(banned=False)

        updated = await users.set_banned(user.xid, banned=True)
        assert updated.banned

    async def test_users_set_admin_promotes_existing_user(self) -> None:
        user = UserFactory.create(is_admin=False)

        updated = await users.set_admin(user.xid, is_admin=True)
        assert updated.is_admin

        DatabaseSession.expire_all()
        fresh = await DatabaseSession.get(User, user.xid)
        assert fresh is not None
        assert fresh.is_admin
        assert fresh.name == user.name

    async def test_users_set_admin_demotes_existing_user(self) -> None:
        user = UserFactory.create(is_admin=True)

        updated = await users.set_admin(user.xid, is_admin=False)
        assert not updated.is_admin

    async def test_users_set_admin_creates_missing_user(self) -> None:
        assert await DatabaseSession.get(User, 9999) is None

        updated = await users.set_admin(9999, is_admin=True)
        assert updated.is_admin
        assert updated.xid == 9999
        assert updated.name == "Unknown User"

    async def test_users_is_admin_true(self) -> None:
        user = UserFactory.create(is_admin=True)
        assert await users.is_admin(user.xid) is True

    async def test_users_is_admin_false(self) -> None:
        user = UserFactory.create(is_admin=False)
        assert await users.is_admin(user.xid) is False

    async def test_users_is_admin_missing_user(self) -> None:
        assert await users.is_admin(8888) is False

    async def test_users_current_game_id(self, game: Game) -> None:
        user = UserFactory.create(game=game)

        user_data = await users.get(user.xid)
        assert user_data is not None
        assert await users.current_game_id(user_data, game.channel_xid) == game.id

    async def test_users_is_waiting(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

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

        await users.block(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        block = (
            await DatabaseSession.execute(
                select(Block).where(
                    Block.user_xid == user1.xid,
                    Block.blocked_user_xid == user2.xid,
                ),
            )
        ).scalar_one()
        assert block.user_xid == user1.xid
        assert block.blocked_user_xid == user2.xid

    async def test_users_unblock(self) -> None:
        user1 = UserFactory.create()
        user2 = UserFactory.create()

        await users.block(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        block = (
            await DatabaseSession.execute(
                select(Block).where(
                    Block.user_xid == user1.xid,
                    Block.blocked_user_xid == user2.xid,
                ),
            )
        ).scalar_one()
        assert block is not None

        await users.unblock(user1.xid, user2.xid)

        DatabaseSession.expire_all()
        block = (
            await DatabaseSession.execute(
                select(Block).where(
                    Block.user_xid == user1.xid,
                    Block.blocked_user_xid == user2.xid,
                ),
            )
        ).scalar_one_or_none()
        assert block is None

    async def test_users_leave_game(self, game: Game) -> None:
        user1 = UserFactory.create(game=game)
        user2 = UserFactory.create()

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Queue))).scalar() or 0
        ) == 1

        user1_data = await users.get(user1.xid)
        assert user1_data is not None
        await users.leave_game(user1_data, game.channel_xid)

        user2_data = await users.get(user2.xid)
        assert user2_data is not None
        await users.leave_game(user2_data, game.channel_xid)

        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Queue))).scalar() or 0
        ) == 0

    async def test_users_current_game_id_deleted_game(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            deleted_at=datetime(2021, 11, 1, tzinfo=UTC),
        )
        user = factories.user.create(game=game)

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

        user_data = await users.get(user.xid)
        assert user_data is not None

        # Queue entry still exists (game was soft-deleted but queue wasn't cleaned up)
        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Queue))).scalar() or 0
        ) == 1

        # leave_game should not find the deleted game, so queue should remain
        await users.leave_game(user_data, channel.xid)

        # Queue entry should still exist since the game was deleted
        assert (
            (await DatabaseSession.execute(select(func.count()).select_from(Queue))).scalar() or 0
        ) == 1

    async def test_set_playgroup_user_id(self) -> None:
        user = UserFactory.create(xid=999)
        assert user.playgroup_user_id is None

        await users.set_playgroup_user_id(user.xid, 4242)

        DatabaseSession.expire_all()
        refreshed = (
            await DatabaseSession.execute(select(User).where(User.xid == user.xid))
        ).scalar_one()
        assert refreshed.playgroup_user_id == 4242


@pytest.mark.asyncio
class TestServiceUsersFilterPendingGames:
    async def test_drops_users_at_their_pending_limit(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        busy = factories.user.create()
        free = factories.user.create()
        bystander = factories.user.create()
        for user in (busy, bystander):
            for _ in range(settings.MAX_PENDING_GAMES - 1):
                game = factories.game.create(guild=guild, channel=channel)
                factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)

        assert await users.filter_pending_games([busy.xid, free.xid]) == [free.xid]


@pytest.mark.asyncio
class TestServiceUsersMoveUser:
    async def test_user_not_found(self) -> None:
        assert await users.move_user(1, 404, 405) == "user not found"

    async def test_user_is_queued(self, factories: Factories) -> None:
        guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)
        assert await users.move_user(guild.xid, user.xid, 999) == "user is queued"

    async def test_moves_user_data(self, factories: Factories) -> None:
        guild = factories.guild.create()
        other_guild = factories.guild.create()
        channel = factories.channel.create(guild=guild)
        other_channel = factories.channel.create(guild=other_guild)
        old = factories.user.create(name="old-name", banned=True)
        friend = factories.user.create()
        foe = factories.user.create()
        factories.block.create(user_xid=old.xid, blocked_user_xid=foe.xid)
        factories.block.create(user_xid=friend.xid, blocked_user_xid=old.xid)
        game = factories.game.create(guild=guild, channel=channel, started_at=datetime.now(tz=UTC))
        other_game = factories.game.create(
            guild=other_guild,
            channel=other_channel,
            started_at=datetime.now(tz=UTC),
        )
        factories.play.create(user_xid=old.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.play.create(user_xid=old.xid, game_id=other_game.id, og_guild_xid=other_guild.xid)
        award = factories.guild_award.create(guild=guild, count=1)
        factories.user_award.create(user_xid=old.xid, guild_xid=guild.xid, guild_award_id=award.id)
        new_xid = old.xid + 1000

        assert await users.move_user(guild.xid, old.xid, new_xid) is None

        DatabaseSession.expire_all()
        new = await DatabaseSession.get(User, new_xid)
        assert new is not None
        assert (new.name, new.banned) == ("old-name", True)
        blocks = (await DatabaseSession.execute(select(Block))).scalars().all()
        assert {(b.user_xid, b.blocked_user_xid) for b in blocks} >= {
            (new_xid, foe.xid),
            (friend.xid, new_xid),
        }
        plays = (
            (await DatabaseSession.execute(select(Play).where(Play.user_xid == new_xid)))
            .scalars()
            .all()
        )
        # Only the plays in the given guild move, keeping where each game was joined from.
        assert [(p.game_id, p.og_guild_xid) for p in plays] == [(game.id, guild.xid)]
        new_award = await DatabaseSession.get(UserAward, (new_xid, guild.xid))
        assert new_award is not None
        assert new_award.guild_award_id == award.id

    async def test_existing_target_user_is_updated(self, factories: Factories) -> None:
        guild = factories.guild.create()
        old = factories.user.create(name="old-name")
        target = factories.user.create(name="target-name")
        assert await users.move_user(guild.xid, old.xid, target.xid) is None
        DatabaseSession.expire_all()
        moved = await DatabaseSession.get(User, target.xid)
        assert moved is not None
        assert moved.name == "old-name"

    async def test_database_error(self, factories: Factories, decoy: Decoy, stub: Stub) -> None:
        guild = factories.guild.create()
        old = factories.user.create()
        commit_fake = stub(DatabaseSession, "commit")
        decoy.when(await commit_fake(), ignore_extra_args=True).then_raise(RuntimeError("boom"))
        rollback = stub(DatabaseSession, "rollback")
        assert await users.move_user(guild.xid, old.xid, old.xid + 1) == "database error"
        decoy.verify(await rollback(), times=1, ignore_extra_args=True)
