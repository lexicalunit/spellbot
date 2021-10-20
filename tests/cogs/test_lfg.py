import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy import update

from spellbot.cogs.lfg import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.interactions import leave_interaction, lfg_interaction
from spellbot.models.game import Game, GameFormat, GameStatus
from spellbot.models.play import Play
from spellbot.models.user import User
from tests.factories.channel import ChannelFactory
from tests.factories.game import GameFactory
from tests.factories.guild import GuildFactory
from tests.factories.play import PlayFactory
from tests.factories.user import UserFactory
from tests.fixtures import build_author, build_channel, build_ctx, build_guild


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_points(self, bot, ctx, settings):
        guild = GuildFactory.create(xid=ctx.guild.id, show_points=True)
        channel = ChannelFactory.create(xid=ctx.channel.id, guild=guild)
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            seats=2,
            status=GameStatus.STARTED.value,
            message_xid=12345,
        )
        DatabaseSession.commit()
        user1 = UserFactory.create(xid=ctx.author.id, game=game)
        user2 = UserFactory.create(game=game)
        DatabaseSession.commit()
        PlayFactory.create(user_xid=user1.xid, game_id=game.id, points=0)
        PlayFactory.create(user_xid=user2.xid, game_id=game.id, points=0)
        DatabaseSession.commit()

        message = MagicMock()
        message.id = game.message_xid
        message.edit = AsyncMock()

        ctx.selected_options = [5]
        ctx.defer = AsyncMock()
        ctx.origin_message = message
        cog = LookingForGameCog(bot)
        await cog.points.func(cog, ctx)

        found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
        assert found.points == 5
        assert message.edit.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": 5914365,
            "description": (
                "Please check your Direct Messages for your SpellTable link.\n\n"
                "When your game is over use the drop down to report your points.\n\n"
                f"{guild.motd}"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{user1.xid}> (5 points), <@{user2.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    async def test_lfg(self, bot, ctx):
        cog = LookingForGameCog(bot)
        await cog._lfg.func(cog, ctx)
        game = DatabaseSession.query(Game).one()
        user = DatabaseSession.query(User).one()
        assert game.channel_xid == ctx.channel.id
        assert game.guild_xid == ctx.guild.id
        assert user.game_id == game.id

    async def test_lfg_when_already_in_game(self, bot, ctx):
        guild = GuildFactory.create(xid=ctx.guild.id)
        channel = ChannelFactory.create(xid=ctx.channel.id, guild=guild)
        user = UserFactory.create(xid=ctx.author.id)
        DatabaseSession.commit()
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()
        user.game = game
        DatabaseSession.commit()

        cog = LookingForGameCog(bot)
        await cog._lfg.func(cog, ctx)
        found = DatabaseSession.query(User).one()
        assert found.game_id == game.id
        ctx.send.assert_called_once_with("You're already in a game.", hidden=True)

    async def test_lfg_with_format(self, bot, ctx):
        cog = LookingForGameCog(bot)
        await cog._lfg.func(cog, ctx, format=GameFormat.MODERN.value)
        game = DatabaseSession.query(Game).one()
        assert game.format == GameFormat.MODERN.value

    async def test_lfg_with_seats(self, bot, ctx):
        cog = LookingForGameCog(bot)
        await cog._lfg.func(cog, ctx, seats=2)
        game = DatabaseSession.query(Game).one()
        assert game.seats == 2

    async def test_lfg_with_friends(self, bot, ctx, monkeypatch):
        friend1 = MagicMock()
        friend1.display_name = "friend1"
        friend1.id = 601

        friend2 = MagicMock()
        friend2.display_name = "friend2"
        friend2.id = 602

        async def safe_fetch_user_mock(bot, xid):
            if xid == friend1.id:
                return friend1
            if xid == friend2.id:
                return friend2
            return None

        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", safe_fetch_user_mock)

        cog = LookingForGameCog(bot)
        await cog._lfg.func(cog, ctx, friends=f"<@{friend1.id}><@{friend2.id}>")
        game = DatabaseSession.query(Game).one()
        users = DatabaseSession.query(User).all()
        assert len(users) == 3
        for user in users:
            assert user.game_id == game.id

    async def test_lfg_with_too_many_friends(self, bot, ctx, monkeypatch):
        friend1 = MagicMock()
        friend1.display_name = "friend1"
        friend1.id = 601

        friend2 = MagicMock()
        friend2.display_name = "friend2"
        friend2.id = 602

        friend3 = MagicMock()
        friend3.display_name = "friend3"
        friend3.id = 603

        friend4 = MagicMock()
        friend4.display_name = "friend4"
        friend4.id = 604

        async def safe_fetch_user_mock(bot, xid):
            if xid == friend1.id:
                return friend1
            if xid == friend2.id:
                return friend2
            if xid == friend3.id:
                return friend3
            if xid == friend4.id:
                return friend4
            return None

        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", safe_fetch_user_mock)

        cog = LookingForGameCog(bot)
        await cog._lfg.func(
            cog,
            ctx,
            friends=f"<@{friend1.id}><@{friend2.id}><@{friend3.id}><@{friend4.id}>",
        )
        game = DatabaseSession.query(Game).one_or_none()
        assert not game

    async def test_join(self, bot, guild, channel, settings, monkeypatch):
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()
        user = UserFactory.create()
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

        sfm_mock = AsyncMock(return_value=message)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_message", sfm_mock)

        sueo_mock = AsyncMock()
        monkeypatch.setattr(lfg_interaction, "safe_update_embed_origin", sueo_mock)

        cog = LookingForGameCog(bot)
        await cog.join.func(cog, ctx)

        sueo_mock.assert_called_once()
        assert sueo_mock.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                f"{guild.motd}"
            ),
            "fields": [
                {"inline": False, "name": "Players", "value": f"<@{user.xid}>"},
                {"inline": True, "name": "Format", "value": "Commander"},
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Waiting for 3 more players to join...**",
            "type": "rich",
        }

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
class TestLFGConcurrency:
    async def test_concurrent_lfg_requests_different_channels(self, bot):
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

    async def test_concurrent_lfg_requests_same_channel(self, bot, monkeypatch):
        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", AsyncMock())

        cog = LookingForGameCog(bot)
        guild = build_guild()
        channel = build_channel(guild)
        default_seats = 4
        n = default_seats * 25
        contexts = [build_ctx(build_author(i), guild, channel, i) for i in range(n)]
        tasks = [cog._lfg.func(cog, contexts[i]) for i in range(n)]
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
