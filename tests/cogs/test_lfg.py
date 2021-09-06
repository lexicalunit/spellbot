import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy import update

from spellbot.cogs.lfg import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.interactions import leave_interaction
from spellbot.models.game import Game
from tests.factories.game import GameFactory
from tests.factories.user import UserFactory
from tests.fixtures import build_author, build_channel, build_ctx, build_guild


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_leave(self, bot, guild, channel, settings, monkeypatch):
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()
        user = UserFactory.create(game=game)
        DatabaseSession.commit()

        author = MagicMock()
        author.id = user.xid
        author.display_name = user.name

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = guild.name

        discord_channel = MagicMock()
        discord_channel.name = channel.name
        discord_channel.id = channel.xid
        discord_channel.guild = discord_guild

        message = MagicMock(spec=discord.Message)
        message.id = 12345

        ctx = AsyncMock()
        ctx.author = author
        ctx.author_id = author.id
        ctx.channel = discord_channel
        ctx.guild = discord_guild
        ctx.guild_id = discord_guild.id
        ctx.message = message
        ctx.origin_message_id = message.id
        ctx.send = AsyncMock()

        query = update(Game).where(Game.id == game.id).values(message_xid=message.id)
        DatabaseSession.execute(query)
        DatabaseSession.commit()

        sftc_mock = AsyncMock(return_value=discord_channel)
        monkeypatch.setattr(leave_interaction, "safe_fetch_text_channel", sftc_mock)

        sfm_mock = AsyncMock(return_value=message)
        monkeypatch.setattr(leave_interaction, "safe_fetch_message", sfm_mock)

        sueo_mock = AsyncMock()
        monkeypatch.setattr(leave_interaction, "safe_update_embed_origin", sueo_mock)

        cog = LookingForGameCog(bot)
        await cog.leave.func(cog, ctx)

        sueo_mock.assert_called_once()
        assert sueo_mock.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                f"{guild.motd}"
            ),
            "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    async def test_leave_message_mismatch(self, bot, guild, channel, monkeypatch):
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()
        user = UserFactory.create(game=game)
        DatabaseSession.commit()

        author = MagicMock()
        author.id = user.xid
        author.display_name = user.name

        discord_guild = MagicMock()
        discord_guild.id = guild.xid
        discord_guild.name = guild.name

        discord_channel = MagicMock()
        discord_channel.name = channel.name
        discord_channel.id = channel.xid
        discord_channel.guild = discord_guild

        message = MagicMock(spec=discord.Message)
        message.id = 12345

        ctx = AsyncMock()
        ctx.author = author
        ctx.author_id = author.id
        ctx.channel = discord_channel
        ctx.guild = discord_guild
        ctx.guild_id = discord_guild.id
        ctx.message = message
        ctx.origin_message_id = message.id
        ctx.send = AsyncMock()

        query = update(Game).where(Game.id == game.id).values(message_xid=message.id + 1)
        DatabaseSession.execute(query)
        DatabaseSession.commit()

        sftc_mock = AsyncMock(return_value=discord_channel)
        monkeypatch.setattr(leave_interaction, "safe_fetch_text_channel", sftc_mock)

        sfm_mock = AsyncMock(return_value=message)
        monkeypatch.setattr(leave_interaction, "safe_fetch_message", sfm_mock)

        cog = LookingForGameCog(bot)
        await cog.leave.func(cog, ctx)

        ctx.send.assert_called_once_with(
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )


@pytest.mark.asyncio
class TestCogLookingForGameConcurrency:
    async def test_concurrent_lfg_requests(self, bot):
        cog = LookingForGameCog(bot)
        guild = build_guild()
        n = 100
        contexts = [
            build_ctx(build_author(i), guild, build_channel(guild, i), i)
            for i in range(n)
        ]
        tasks = [cog._lfg.func(cog, contexts[i]) for i in range(n)]
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
