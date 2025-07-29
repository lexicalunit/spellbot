from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spellbot.actions import lfg_action
from spellbot.cogs import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Game
from tests.mocks import build_author, build_channel, build_guild, build_interaction

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from spellbot import SpellBot

pytestmark = pytest.mark.use_db


async def run_lfg(cog: LookingForGameCog, interaction: discord.Interaction) -> None:
    command = cog.lfg
    callback = command.callback
    if command.binding:  # pragma: no cover
        callback = partial(callback, command.binding)
    callback = cast("Callable[..., Awaitable[None]]", callback)
    return await callback(interaction=interaction)


@pytest.mark.asyncio
class TestCogLookingForGameConcurrency:
    async def test_concurrent_lfg_requests_different_channels(self, bot: SpellBot) -> None:
        cog = LookingForGameCog(bot)
        guild = build_guild()
        n = 100
        interactions = [
            build_interaction(guild, build_channel(guild, i), build_author(i)) for i in range(n)
        ]
        tasks = [asyncio.create_task(run_lfg(cog, interactions[i])) for i in range(n)]

        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()

        games = DatabaseSession.query(Game).order_by(Game.created_at).all()
        assert len(games) == n

        # Since all these lfg requests should be handled concurrently, we should
        # see message_xids OUT of order in the created games (as ordered by created at).
        messages_out_of_order = False
        message_xid: int | None = None
        for game in games:  # pragma: no cover
            if message_xid and game.posts[0].message_xid != message_xid + 1:
                # At least one game is out of order, this is good!
                messages_out_of_order = True
                break
            message_xid = game.posts[0].message_xid
        assert messages_out_of_order

    async def test_concurrent_lfg_requests_same_channel(
        self,
        bot: SpellBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        next_message_xid = 1

        def get_next_message(*args: Any, **kwargs: Any) -> discord.Message:
            nonlocal next_message_xid
            message = MagicMock(spec=discord.Message)
            message.id = next_message_xid
            next_message_xid += 1
            return message

        monkeypatch.setattr(lfg_action, "safe_fetch_user", AsyncMock())
        monkeypatch.setattr(
            lfg_action,
            "safe_followup_channel",
            AsyncMock(side_effect=get_next_message),
        )
        monkeypatch.setattr(
            lfg_action,
            "safe_get_partial_message",
            MagicMock(side_effect=get_next_message),
        )
        monkeypatch.setattr(lfg_action, "safe_update_embed_origin", AsyncMock(return_value=True))
        monkeypatch.setattr(lfg_action, "safe_update_embed", AsyncMock(return_value=True))

        cog = LookingForGameCog(bot)
        guild = build_guild()
        channel = build_channel(guild)
        default_seats = 4
        n = default_seats * 25
        interactions = [build_interaction(guild, channel, build_author(i)) for i in range(n)]
        tasks = [asyncio.create_task(run_lfg(cog, interactions[i])) for i in range(n)]

        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()

        games = DatabaseSession.query(Game).order_by(Game.created_at).all()
        assert len(games) == n / default_seats

        # Since all these lfg requests should be handled concurrently, we should
        # see message_xids OUT of order in the created games (as ordered by created at).
        messages_out_of_order = False
        message_xid: int | None = None
        for game in games:  # pragma: no cover
            if message_xid is not None and game.posts[0].message_xid != message_xid + 1:
                # At least one game is out of order, this is good!
                messages_out_of_order = True
                break
            message_xid = game.posts[0].message_xid
        assert messages_out_of_order
