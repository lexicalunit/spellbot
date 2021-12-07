from unittest.mock import AsyncMock

import pytest

from spellbot.database import DatabaseSession
from spellbot.interactions import LookingForGameInteraction, lfg_interaction
from spellbot.models import User
from tests.mixins import InteractionContextMixin
from tests.mocks import build_author, mock_discord_user, mock_operations


@pytest.mark.asyncio
class TestInteractionLookingForGame(InteractionContextMixin):
    async def test_ensure_users_happy_path(self, monkeypatch):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())

        async def fetch_user(_, xid):
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(self.bot, self.ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids)
            assert set(created) == set(
                user.id for user in user_list if user.id != self.ctx.author_id
            )

        assert DatabaseSession.query(User).count() == 3

    async def test_ensure_users_without_exclude_self(self, monkeypatch):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())

        async def fetch_user(_, xid):
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(self.bot, self.ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids, exclude_self=False)
            assert set(created) == set(user_xids)

        assert DatabaseSession.query(User).count() == 3

    async def test_ensure_users_when_fetch_user_fails(self, monkeypatch):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())

        async def fetch_user(_, xid):
            if xid == user_list[-1].id:
                return None
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(self.bot, self.ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids, exclude_self=False)
            assert set(created) == set(
                user.id for user in user_list if user.id != user_list[-1].id
            )

        assert DatabaseSession.query(User).count() == 2

    async def test_ensure_users_when_user_banned(self, monkeypatch):
        user_list = [build_author(xid) for xid in range(1, 4)]
        user_dict = {user.id: user for user in user_list}
        user_xids = list(user_dict.keys())
        banned_user_xid = user_list[-1].id
        self.factories.user.create(xid=banned_user_xid, banned=True)

        async def fetch_user(_, xid):
            return user_dict[xid]

        mock_sfu = AsyncMock(side_effect=fetch_user)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", mock_sfu)

        async with LookingForGameInteraction.create(self.bot, self.ctx) as interaction:
            created = await interaction.ensure_users_exist(user_xids, exclude_self=False)
            assert set(created) == set(
                user.id for user in user_list if user.id != banned_user_xid
            )

        assert DatabaseSession.query(User).count() == 3

    async def test_lfg_in_a_thread(self, monkeypatch):
        guild = self.factories.guild.create(xid=self.ctx.guild_id)
        self.factories.channel.create(xid=self.ctx.channel_id, guild=guild)
        author_user = self.factories.user.create(xid=self.ctx.author_id)
        author_player = mock_discord_user(author_user)

        # ctx.channel is None when handling an interaction in a Thread.
        monkeypatch.setattr(self.ctx, "channel", None)

        async with LookingForGameInteraction.create(self.bot, self.ctx) as interaction:
            with mock_operations(lfg_interaction, users=[author_player]):
                await interaction.execute()
                lfg_interaction.safe_send_channel.assert_called_once_with(
                    self.ctx,
                    "Sorry, that command is not supported in this context.",
                    hidden=True,
                )
