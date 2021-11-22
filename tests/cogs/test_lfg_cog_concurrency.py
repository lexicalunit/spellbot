import asyncio
from typing import Optional
from unittest.mock import AsyncMock

import pytest

from spellbot import SpellBot
from spellbot.cogs.lfg_cog import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.interactions import lfg_interaction
from spellbot.models import Game
from tests.mocks import build_author, build_channel, build_ctx, build_guild


@pytest.mark.asyncio
class TestCogLookingForGameConcurrency:
    async def test_concurrent_lfg_requests_different_channels(self, bot: SpellBot):
        cog = LookingForGameCog(bot)
        guild = build_guild()
        n = 100
        contexts = [
            build_ctx(guild, build_channel(guild, i), build_author(i), i)
            for i in range(n)
        ]
        tasks = [cog.lfg.func(cog, contexts[i]) for i in range(n)]
        await asyncio.wait(tasks)

        games = DatabaseSession.query(Game).order_by(Game.created_at).all()
        assert len(games) == n

        # Since all these lfg requests should be handled concurrently, we should
        # see message_xids OUT of order in the created games (as ordered by created at).
        messages_out_of_order = False
        message_xid: Optional[int] = None
        for game in games:
            if message_xid is not None and game.message_xid != message_xid + 1:
                # At leat one game is out of order, this is good!
                messages_out_of_order = True
                break
            message_xid = game.message_xid
        assert messages_out_of_order

    async def test_concurrent_lfg_requests_same_channel(self, bot: SpellBot, monkeypatch):
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", AsyncMock())

        cog = LookingForGameCog(bot)
        guild = build_guild()
        channel = build_channel(guild)
        default_seats = 4
        n = default_seats * 25
        contexts = [build_ctx(guild, channel, build_author(i), i) for i in range(n)]
        tasks = [cog.lfg.func(cog, contexts[i]) for i in range(n)]
        await asyncio.wait(tasks)

        games = DatabaseSession.query(Game).order_by(Game.created_at).all()
        assert len(games) == n / default_seats

        # Since all these lfg requests should be handled concurrently, we should
        # see message_xids OUT of order in the created games (as ordered by created at).
        messages_out_of_order = False
        message_xid: Optional[int] = None
        for game in games:
            if message_xid is not None and game.message_xid != message_xid + 1:
                # At leat one game is out of order, this is good!
                messages_out_of_order = True
                break
            message_xid = game.message_xid
        assert messages_out_of_order
