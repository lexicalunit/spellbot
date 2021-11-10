from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot
from spellbot.cogs.leave import LeaveGameCog
from spellbot.interactions import leave_interaction
from spellbot.models import Channel, Guild
from spellbot.settings import Settings
from tests.fixtures import Factories

# TODO: Rewrite these tests using mock_operations().


@pytest.mark.asyncio
class TestCogLeaveGame:
    async def test_leave(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
        monkeypatch,
    ):
        game = factories.game.create(guild=guild, channel=channel)
        factories.user.create(xid=ctx.author_id, name=ctx.author.display_name, game=game)

        sftc_mock = AsyncMock(return_value=ctx.channel)
        monkeypatch.setattr(leave_interaction, "safe_fetch_text_channel", sftc_mock)

        sfm_mock = AsyncMock(return_value=ctx.message)
        monkeypatch.setattr(leave_interaction, "safe_fetch_message", sfm_mock)

        sue_mock = AsyncMock()
        monkeypatch.setattr(leave_interaction, "safe_update_embed", sue_mock)

        cog = LeaveGameCog(bot)
        await cog.leave.func(cog, ctx)

        ctx.send.assert_called_once_with(
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )
        sue_mock.assert_called_once()
        assert sue_mock.call_args_list[0].kwargs["embed"].to_dict() == {
            "color": settings.EMBED_COLOR,
            "description": (
                "_A SpellTable link will be created when all players have joined._\n"
                "\n"
                f"{guild.motd}\n\n{channel.motd}"
            ),
            "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
            "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
            "thumbnail": {"url": settings.THUMB_URL},
            "title": "**Waiting for 4 more players to join...**",
            "type": "rich",
        }

    async def test_leave_when_no_message_xid(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
    ):
        game = factories.game.create(guild=guild, channel=channel, message_xid=None)
        factories.user.create(xid=ctx.author_id, name=ctx.author.display_name, game=game)

        sftc_mock = AsyncMock(return_value=ctx.channel)
        monkeypatch.setattr(leave_interaction, "safe_fetch_text_channel", sftc_mock)

        cog = LeaveGameCog(bot)
        await cog.leave.func(cog, ctx)

        ctx.send.assert_called_once_with(
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )

    async def test_leave_when_not_in_game(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        factories.user.create(xid=ctx.author_id, name=ctx.author.display_name)

        cog = LeaveGameCog(bot)
        await cog.leave.func(cog, ctx)

        ctx.send.assert_called_once_with(
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )

    async def test_leave_when_no_channel(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        monkeypatch,
    ):
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)

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

        discord_message = MagicMock(spec=discord.Message)
        discord_message.id = 12345

        ctx = AsyncMock()
        ctx.author = author
        ctx.author_id = author.id
        ctx.channel = discord_channel
        ctx.guild = discord_guild
        ctx.guild_id = discord_guild.id
        ctx.message = discord_message
        ctx.send = AsyncMock()

        sftc_mock = AsyncMock(return_value=None)
        monkeypatch.setattr(leave_interaction, "safe_fetch_text_channel", sftc_mock)

        cog = LeaveGameCog(bot)
        await cog.leave.func(cog, ctx)

        ctx.send.assert_called_once_with(
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )

    async def test_leave_when_no_message(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        monkeypatch,
    ):
        game = factories.game.create(guild=guild, channel=channel)
        user = factories.user.create(game=game)

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

        discord_message = MagicMock(spec=discord.Message)
        discord_message.id = 12345

        ctx = AsyncMock()
        ctx.author = author
        ctx.author_id = author.id
        ctx.channel = discord_channel
        ctx.guild = discord_guild
        ctx.guild_id = discord_guild.id
        ctx.message = discord_message
        ctx.send = AsyncMock()

        sftc_mock = AsyncMock(return_value=discord_channel)
        monkeypatch.setattr(leave_interaction, "safe_fetch_text_channel", sftc_mock)

        sfm_mock = AsyncMock(return_value=None)
        monkeypatch.setattr(leave_interaction, "safe_fetch_message", sfm_mock)

        cog = LeaveGameCog(bot)
        await cog.leave.func(cog, ctx)

        ctx.send.assert_called_once_with(
            "You have been removed from any games your were signed up for.",
            hidden=True,
        )
