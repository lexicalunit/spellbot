from unittest.mock import AsyncMock

import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot
from spellbot.database import DatabaseSession
from spellbot.interactions import LookingForGameInteraction, lfg_interaction
from spellbot.models import User
from tests.fixtures import Factories
from tests.mocks import build_author

# TODO: Rewrite these tests using mock_operations().


@pytest.mark.asyncio
class TestInteractionLookingForGame:
    async def test_ensure_users_happy_path(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        monkeypatch,
    ):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())

        async def fetch_user(_, xid):
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(bot, ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids)
            assert set(created) == set(
                [user.id for user in user_list if user.id != ctx.author_id]
            )

        assert DatabaseSession.query(User).count() == 3

    async def test_ensure_users_without_exclude_self(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        monkeypatch,
    ):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())

        async def fetch_user(_, xid):
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(bot, ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids, exclude_self=False)
            assert set(created) == set(user_xids)

        assert DatabaseSession.query(User).count() == 3

    async def test_ensure_users_when_fetch_user_fails(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        monkeypatch,
    ):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())

        async def fetch_user(_, xid):
            if xid == user_list[-1].id:
                return None
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(bot, ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids, exclude_self=False)
            assert set(created) == set(
                [user.id for user in user_list if user.id != user_list[-1].id]
            )

        assert DatabaseSession.query(User).count() == 2

    async def test_ensure_users_when_user_banned(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
    ):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())
        banned_user_xid = user_list[-1].id
        factories.user.create(xid=banned_user_xid, banned=True)

        async def fetch_user(_, xid):
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(bot, ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids, exclude_self=False)
            assert set(created) == set(
                [user.id for user in user_list if user.id != banned_user_xid]
            )

        assert DatabaseSession.query(User).count() == 3
