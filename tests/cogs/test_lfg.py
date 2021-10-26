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
from tests.factories.block import BlockFactory
from tests.factories.channel import ChannelFactory
from tests.factories.game import GameFactory
from tests.factories.guild import GuildFactory
from tests.factories.play import PlayFactory
from tests.factories.user import UserFactory
from tests.fixtures import (
    build_author,
    build_channel,
    build_client_user,
    build_ctx,
    build_guild,
    build_message,
    build_response,
    build_voice_channel,
    channel_from_ctx,
    game_from_ctx,
    guild_from_ctx,
    mock_discord_user,
    mock_operations,
    user_from_ctx,
)


@pytest.mark.asyncio
class TestCogLookingForGamePoints:
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

    async def test_points_when_message_not_found(self, bot, ctx):
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
        message.id = game.message_xid + 10  # +10 so that it won't be found
        message.edit = AsyncMock()

        ctx.selected_options = [5]
        ctx.defer = AsyncMock()
        ctx.origin_message = message
        cog = LookingForGameCog(bot)
        await cog.points.func(cog, ctx)

        found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
        assert found.points == 0  # hasn't changed

    async def test_points_when_not_in_game(self, bot, ctx):
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
        UserFactory.create(xid=ctx.author.id)
        user2 = UserFactory.create(game=game)
        DatabaseSession.commit()
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

        ctx.send.assert_called_once_with(
            "You are not one of the players in this game.",
            hidden=True,
        )


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_lfg(self, bot, ctx):
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx)
        game = DatabaseSession.query(Game).one()
        user = DatabaseSession.query(User).one()
        assert game.channel_xid == ctx.channel.id
        assert game.guild_xid == ctx.guild.id
        assert user.game_id == game.id

    async def test_lfg_fully_seated(self, bot, ctx, monkeypatch, settings):
        guild = GuildFactory.create(xid=ctx.guild.id)
        channel = ChannelFactory.create(xid=ctx.channel.id, guild=guild, default_seats=2)
        author_user = UserFactory.create(xid=ctx.author.id)
        other_user = UserFactory.create(xid=ctx.author.id + 1)
        DatabaseSession.commit()
        game = GameFactory.create(guild=guild, channel=channel, seats=2, message_xid=123)
        DatabaseSession.commit()
        other_user.game = game
        DatabaseSession.commit()

        author_player = MagicMock(spec=discord.Member)
        author_player.id = author_user.xid
        author_player.display_name = author_user.name
        author_player.mention = f"<@{author_player.id}>"
        author_player.send = AsyncMock()

        other_player = MagicMock(spec=discord.Member)
        other_player.id = other_user.xid
        other_player.display_name = other_user.name
        other_player.mention = f"<@{other_player.id}>"
        other_player.send = AsyncMock()

        async def safe_fetch_user_mock(_, xid):
            if xid == author_player.id:
                return author_player
            if xid == other_player.id:
                return other_player
            return None

        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", safe_fetch_user_mock)

        message = MagicMock(spec=discord.Message)
        message.id = game.message_xid
        sfm_mock = AsyncMock(return_value=message)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_message", sfm_mock)

        sueo_mock = AsyncMock()
        monkeypatch.setattr(lfg_interaction, "safe_update_embed_origin", sueo_mock)

        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx)

        assert ctx.send.call_args_list[0].kwargs["embed"].to_dict() == {
            "author": {"name": "I found a game for you!"},
            "color": settings.EMBED_COLOR,
            "description": (
                "You can [jump to the game post](https://discordapp.com/channels/"
                f"{guild.xid}/{channel.xid}/{message.id}) to see it!"
            ),
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

    async def test_lfg_when_blocked(self, bot, ctx):
        guild = GuildFactory.create(xid=ctx.guild.id)
        channel = ChannelFactory.create(xid=ctx.channel.id, guild=guild)
        author_user = UserFactory.create(xid=ctx.author.id)
        other_user = UserFactory.create(xid=ctx.author.id + 1)
        DatabaseSession.commit()
        game = GameFactory.create(guild=guild, channel=channel)
        DatabaseSession.commit()
        other_user.game = game
        DatabaseSession.commit()
        BlockFactory.create(user_xid=other_user.xid, blocked_user_xid=author_user.xid)
        DatabaseSession.commit()

        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx)
        other_game = DatabaseSession.query(Game).filter(Game.id == game.id).one_or_none()
        assert other_game
        author_game = DatabaseSession.query(Game).filter(Game.id != game.id).one_or_none()
        assert author_game
        assert other_game != author_game

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
        await cog.lfg.func(cog, ctx)
        found = DatabaseSession.query(User).one()
        assert found.game_id == game.id
        ctx.send.assert_called_once_with("You're already in a game.", hidden=True)

    async def test_lfg_with_format(self, bot, ctx):
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx, format=GameFormat.MODERN.value)
        game = DatabaseSession.query(Game).one()
        assert game.format == GameFormat.MODERN.value

    async def test_lfg_with_seats(self, bot, ctx):
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx, seats=2)
        game = DatabaseSession.query(Game).one()
        assert game.seats == 2

    async def test_lfg_with_friends(self, bot, ctx, monkeypatch):
        friend1 = MagicMock()
        friend1.display_name = "friend1"
        friend1.id = 601

        friend2 = MagicMock()
        friend2.display_name = "friend2"
        friend2.id = 602

        async def safe_fetch_user_mock(_, xid):
            if xid == friend1.id:
                return friend1
            if xid == friend2.id:
                return friend2
            return None

        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", safe_fetch_user_mock)

        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx, friends=f"<@{friend1.id}><@{friend2.id}>")
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

        async def safe_fetch_user_mock(_, xid):
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
        await cog.lfg.func(
            cog,
            ctx,
            friends=f"<@{friend1.id}><@{friend2.id}><@{friend3.id}><@{friend4.id}>",
        )
        game = DatabaseSession.query(Game).one_or_none()
        assert not game

    async def test_lfg_multiple_times(self, bot):
        guild = build_guild()
        channel = build_channel(guild=guild)
        author1 = build_author(1)
        author2 = build_author(2)

        ctx1 = MagicMock()
        ctx1.author = author1
        ctx1.author_id = author1.id
        ctx1.guild = guild
        ctx1.guild_id = guild.id
        ctx1.channel = channel
        ctx1.channel_id = channel.id
        ctx1.message = build_message(guild, channel, author1, 1)
        ctx1.send = AsyncMock(return_value=build_response(guild, channel, 1))

        ctx2 = MagicMock()
        ctx2.author = author2
        ctx2.author_id = author2.id
        ctx2.guild = guild
        ctx2.guild_id = guild.id
        ctx2.channel = channel
        ctx2.channel_id = channel.id
        ctx2.message = build_message(guild, channel, author2, 2)
        ctx2.send = AsyncMock(return_value=build_response(guild, channel, 2))

        client_user = build_client_user()
        game_post = build_message(guild, channel, client_user, 3)

        cog = LookingForGameCog(bot)

        with mock_operations(lfg_interaction, users=[author1, author2]):
            lfg_interaction.safe_send_channel.return_value = game_post
            await cog.lfg.func(cog, ctx1, seats=2)

        with mock_operations(lfg_interaction, users=[author1, author2]):
            await cog.lfg.func(cog, ctx2, seats=2)

        game = DatabaseSession.query(Game).one()
        assert game.to_dict() == {
            "channel_xid": channel.id,
            "created_at": game.created_at,
            "format": game.format,
            "guild_xid": guild.id,
            "id": game.id,
            "jump_link": game.jump_link,
            "message_xid": game_post.id,
            "seats": 2,
            "spectate_link": game.spectate_link,
            "spelltable_link": game.spelltable_link,
            "started_at": game.started_at,
            "status": GameStatus.STARTED.value,
            "updated_at": game.updated_at,
            "voice_invite_link": None,
            "voice_xid": None,
        }


@pytest.mark.asyncio
class TestCogLookingForGameJoinButton:
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

    async def test_join_with_show_points(self, bot, ctx, settings, snapshot, monkeypatch):
        guild = GuildFactory.create(xid=ctx.guild.id, show_points=True)
        channel = ChannelFactory.create(xid=ctx.channel.id, guild=guild)
        author_user = UserFactory.create(xid=ctx.author.id)
        other_user = UserFactory.create(xid=ctx.author.id + 1)
        DatabaseSession.commit()
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            seats=2,
            message_xid=ctx.message.id,
        )
        DatabaseSession.commit()
        other_user.game = game
        DatabaseSession.commit()

        ctx.origin_message = ctx.message
        ctx.origin_message_id = ctx.message.id
        other_player = MagicMock(spec=discord.Member)
        other_player.id = other_user.xid
        other_player.display_name = other_user.name
        other_player.mention = f"<@{other_player.id}>"
        other_player.send = AsyncMock()

        sfm_mock = AsyncMock(return_value=ctx.message)
        monkeypatch.setattr(lfg_interaction, "safe_fetch_message", sfm_mock)

        sueo_mock = AsyncMock()
        monkeypatch.setattr(lfg_interaction, "safe_update_embed_origin", sueo_mock)

        async def safe_fetch_user_mock(_, xid):
            if xid == other_user.xid:
                return other_player
            if xid == author_user.xid:
                return ctx.author
            return None

        monkeypatch.setattr(lfg_interaction, "safe_fetch_user", safe_fetch_user_mock)

        cog = LookingForGameCog(bot)
        await cog.join.func(cog, ctx)

        sueo_mock.assert_called_once()
        assert sueo_mock.call_args_list[0].kwargs["components"] == snapshot
        assert sueo_mock.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "Please check your Direct Messages for your SpellTable link.\n\n"
                "When your game is over use the drop down to report your points.\n\n"
                f"{guild.motd}"
            ),
            "fields": [
                {
                    "inline": False,
                    "name": "Players",
                    "value": f"<@{ctx.author.id}>, <@{other_user.xid}>",
                },
                {"inline": True, "name": "Format", "value": "Commander"},
                {
                    "inline": True,
                    "name": "Started at",
                    "value": f"<t:{game.started_at_timestamp}>",
                },
            ],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Your game is ready!**",
            "type": "rich",
        }

    async def test_join_when_blocked(self, bot, ctx):
        guild = GuildFactory.create(xid=ctx.guild.id)
        channel = ChannelFactory.create(xid=ctx.channel.id, guild=guild)
        author_user = UserFactory.create(xid=ctx.author.id)
        other_user = UserFactory.create(xid=ctx.author.id + 1)
        DatabaseSession.commit()
        game = GameFactory.create(
            guild=guild,
            channel=channel,
            message_xid=ctx.message.id,
        )
        DatabaseSession.commit()
        other_user.game = game
        DatabaseSession.commit()
        BlockFactory.create(user_xid=other_user.xid, blocked_user_xid=author_user.xid)
        DatabaseSession.commit()

        ctx.origin_message_id = ctx.message.id
        cog = LookingForGameCog(bot)
        await cog.join.func(cog, ctx)

        games = DatabaseSession.query(Game).all()
        assert len(games) == 1
        ctx.send.assert_called_once_with("You can not join this game.", hidden=True)


@pytest.mark.asyncio
class TestCogLookingForGameLeaveButton:
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

    async def test_leave_message_mismatch(self, bot, ctx):
        ctx.set_origin()

        guild = guild_from_ctx(ctx)
        channel = channel_from_ctx(ctx, guild)
        game = game_from_ctx(ctx, guild, channel, seats=2)
        user_from_ctx(ctx, xid=ctx.author.id, game=game)

        wrong_xid = ctx.message.id + 1
        query = update(Game).where(Game.id == game.id).values(message_xid=wrong_xid)
        DatabaseSession.execute(query)
        DatabaseSession.commit()

        with mock_operations(leave_interaction, users=[ctx.author]):
            leave_interaction.safe_fetch_text_channel.return_value = ctx.channel
            leave_interaction.safe_fetch_message.return_value = ctx.message

            cog = LookingForGameCog(bot)
            await cog.leave.func(cog, ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )


@pytest.mark.asyncio
class TestCogLookingForGameVoiceCreate:
    async def test_join_happy_path(self, bot, ctx):
        ctx.set_origin()

        guild = guild_from_ctx(ctx, voice_create=True)
        channel = channel_from_ctx(ctx, guild)
        game = game_from_ctx(ctx, guild, channel, seats=2)
        other_user = user_from_ctx(ctx, xid=ctx.author.id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = ctx.message
            voice_channel = build_voice_channel(ctx.guild)
            lfg_interaction.safe_create_voice_channel.return_value = voice_channel
            lfg_interaction.safe_create_invite.return_value = "http://invite"

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, ctx)

        found = DatabaseSession.query(Game).one()
        assert found.voice_xid == voice_channel.id
        assert found.voice_invite_link == "http://invite"

    async def test_join_when_category_fails(self, bot, ctx):
        ctx.set_origin()

        guild = guild_from_ctx(ctx, voice_create=True)
        channel = channel_from_ctx(ctx, guild)
        game = game_from_ctx(ctx, guild, channel, seats=2)
        other_user = user_from_ctx(ctx, xid=ctx.author.id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = ctx.message
            lfg_interaction.safe_ensure_voice_category.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, ctx)

        found = DatabaseSession.query(Game).one()
        assert not found.voice_xid
        assert not found.voice_invite_link

    async def test_join_when_channel_fails(self, bot, ctx):
        ctx.set_origin()

        guild = guild_from_ctx(ctx, voice_create=True)
        channel = channel_from_ctx(ctx, guild)
        game = game_from_ctx(ctx, guild, channel, seats=2)
        other_user = user_from_ctx(ctx, xid=ctx.author.id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = ctx.message
            lfg_interaction.safe_create_voice_channel.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, ctx)

        found = DatabaseSession.query(Game).one()
        assert not found.voice_xid
        assert not found.voice_invite_link

    async def test_join_when_invite_fails(self, bot, ctx):
        ctx.set_origin()

        guild = guild_from_ctx(ctx, voice_create=True)
        channel = channel_from_ctx(ctx, guild)
        game = game_from_ctx(ctx, guild, channel, seats=2)
        other_user = user_from_ctx(ctx, xid=ctx.author.id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = ctx.message
            voice_channel = build_voice_channel(ctx.guild)
            lfg_interaction.safe_create_voice_channel.return_value = voice_channel
            lfg_interaction.safe_create_invite.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, ctx)

        found = DatabaseSession.query(Game).one()
        assert found.voice_xid == voice_channel.id
        assert not found.voice_invite_link


@pytest.mark.asyncio
class TestCogLookingForGameConcurrency:
    async def test_concurrent_lfg_requests_different_channels(self, bot):
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

    async def test_concurrent_lfg_requests_same_channel(self, bot, monkeypatch):
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
