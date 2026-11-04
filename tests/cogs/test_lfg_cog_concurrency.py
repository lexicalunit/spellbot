# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, cast

import discord
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from spellbot.actions import game_posts, game_start, lfg_action
from spellbot.cogs import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Game
from tests.mocks import decoys

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from decoy import Decoy
    from discord.abc import MessageableChannel

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
    async def test_concurrent_lfg_requests_different_channels(
        self,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        cog = LookingForGameCog(bot)
        guild = decoys.guild(decoy)
        n = 100
        interactions = [
            await decoys.interaction(
                decoy,
                guild,
                decoys.channel(decoy, guild, offset=i),
                decoys.member(decoy, offset=i),
            )
            for i in range(n)
        ]
        tasks = [asyncio.create_task(run_lfg(cog, interactions[i])) for i in range(n)]

        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()

        games = list(
            (
                await DatabaseSession.execute(
                    select(Game).options(selectinload(Game.posts)).order_by(Game.created_at),
                )
            )
            .scalars()
            .all(),
        )
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
        decoy: Decoy,
    ) -> None:
        next_message_xid = 1

        def next_message() -> discord.Message:
            nonlocal next_message_xid
            message = decoy.mock(cls=discord.Message)
            message.id = next_message_xid
            next_message_xid += 1
            return message

        def get_partial_message(
            channel: MessageableChannel,
            guild_xid: int,
            message_xid: int,
        ) -> discord.Message:
            return next_message()

        async def followup_channel(
            interaction: discord.Interaction,
            *content: str,
            **kwargs: str | discord.Embed | discord.ui.View | None,
        ) -> discord.Message:
            return next_message()

        fakes = {
            "safe_fetch_user": decoys.async_returning(None),
            "safe_followup_channel": followup_channel,
            "safe_get_partial_message": get_partial_message,
            "safe_update_embed_origin": decoys.async_returning(True),
            "safe_update_embed": decoys.async_returning(True),
        }
        # The /lfg flow calls these from `lfg_action` and its helper modules.
        for module in (lfg_action, game_posts, game_start):
            for name, fake in fakes.items():
                if hasattr(module, name):
                    monkeypatch.setattr(module, name, fake)

        cog = LookingForGameCog(bot)
        guild = decoys.guild(decoy)
        channel = decoys.channel(decoy, guild)
        default_seats = 4
        n = default_seats * 25
        interactions = [
            await decoys.interaction(decoy, guild, channel, decoys.member(decoy, offset=i))
            for i in range(n)
        ]
        tasks = [asyncio.create_task(run_lfg(cog, interactions[i])) for i in range(n)]

        done, pending = await asyncio.wait(tasks)
        assert not pending
        for future in done:
            future.result()

        games = list(
            (
                await DatabaseSession.execute(
                    select(Game).options(selectinload(Game.posts)).order_by(Game.created_at),
                )
            )
            .scalars()
            .all(),
        )
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
