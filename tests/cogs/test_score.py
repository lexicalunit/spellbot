from unittest.mock import AsyncMock, MagicMock

import pytest

from spellbot.cogs.score import ScoreCog
from spellbot.database import DatabaseSession
from spellbot.models.game import Game
from spellbot.models.play import Play
from tests.fixtures import build_channel, build_ctx, build_guild


@pytest.mark.asyncio
class TestCogScore:
    async def test_score(self, bot, ctx, settings):
        cog = ScoreCog(bot)
        await cog.score.func(cog, ctx)
        ctx.send.assert_called_once()
        embed = ctx.send.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Record of games played on {ctx.guild.name}"},
            "color": settings.EMBED_COLOR,
            "description": f"<@{ctx.author.id}> has played 0 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{ctx.guild.id}/u/{ctx.author.id}).",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

        game = Game(seats=2, guild_xid=ctx.guild.id, channel_xid=ctx.channel.id)
        DatabaseSession.add(game)
        DatabaseSession.commit()
        DatabaseSession.add(Play(user_xid=ctx.author.id, game_id=game.id))
        DatabaseSession.commit()

        ctx.send = AsyncMock()
        await cog.score.func(cog, ctx)
        ctx.send.assert_called_once()
        embed = ctx.send.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Record of games played on {ctx.guild.name}"},
            "color": settings.EMBED_COLOR,
            "description": f"<@{ctx.author.id}> has played 1 game on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{ctx.guild.id}/u/{ctx.author.id}).",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

        game = Game(seats=2, guild_xid=ctx.guild.id, channel_xid=ctx.channel.id)
        DatabaseSession.add(game)
        DatabaseSession.commit()
        DatabaseSession.add(Play(user_xid=ctx.author.id, game_id=game.id))
        DatabaseSession.commit()

        ctx.send = AsyncMock()
        await cog.score.func(cog, ctx)
        ctx.send.assert_called_once()
        embed = ctx.send.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Record of games played on {ctx.guild.name}"},
            "color": settings.EMBED_COLOR,
            "description": f"<@{ctx.author.id}> has played 2 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{ctx.guild.id}/u/{ctx.author.id}).",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

        new_guild = build_guild(2)
        new_channel = build_channel(new_guild, 2)
        new_ctx = build_ctx(new_guild, new_channel, ctx.author, 2)
        await cog.score.func(cog, new_ctx)
        new_ctx.send.assert_called_once()
        embed = new_ctx.send.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Record of games played on {new_ctx.guild.name}"},
            "color": settings.EMBED_COLOR,
            "description": f"<@{new_ctx.author.id}> has played 0 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{new_ctx.guild.id}/u/{new_ctx.author.id}).",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

    async def test_view_score(self, bot, ctx, settings):
        target_author = MagicMock()
        target_author.id = 1002
        target_author.display_name = "target-author-display-name"
        target_author.mention = f"<@{target_author.id}>"
        ctx.target_author = target_author
        ctx.target_author_id = target_author.id

        cog = ScoreCog(bot)
        await cog.view_score.func(cog, ctx)

        ctx.send.assert_called_once()
        embed = ctx.send.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Record of games played on {ctx.guild.name}"},
            "color": settings.EMBED_COLOR,
            "description": f"<@{target_author.id}> has played 0 games on this server.\n"
            "View more [details on spellbot.io]"
            f"(https://bot.spellbot.io/g/{ctx.guild.id}/u/{target_author.id}).",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }

    async def test_history(self, bot, ctx, settings):
        cog = ScoreCog(bot)
        await cog.history.func(cog, ctx)

        ctx.send.assert_called_once()
        embed = ctx.send.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.to_dict() == {
            "author": {"name": f"Recent games played in {ctx.channel.name}"},
            "color": settings.EMBED_COLOR,
            "description": "View [game history on spellbot.io]"
            f"(https://bot.spellbot.io/g/{ctx.guild.id}/c/{ctx.channel.id}).",
            "thumbnail": {"url": settings.ICO_URL},
            "type": "rich",
        }