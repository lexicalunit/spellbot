from __future__ import annotations

# TODO
# from unittest.mock import AsyncMock, MagicMock

# import pytest

# from spellbot import SpellBot
# from spellbot.cogs import LookingForGameCog
# from spellbot.database import DatabaseSession
# from spellbot.actions import lfg_action
# from spellbot.models import GameStatus, Play
# from spellbot.settings import Settings
# from tests.fixtures import Factories
# from tests.mocks import mock_discord_user, mock_operations


# @pytest.mark.asyncio()
# class TestCogLookingForGamePoints:
#     async def test_points(
#         self,
#         bot: SpellBot,
#         ctx: ComponentContext,
#         settings: Settings,
#         factories: Factories,
#     ):
#         guild = factories.guild.create(xid=ctx.guild_id, show_points=True)
#         channel = factories.channel.create(xid=ctx.channel_id, guild=guild)
#         game = factories.game.create(
#             guild=guild,
#             channel=channel,
#             seats=2,
#             status=GameStatus.STARTED.value,
#             message_xid=12345,
#         )
#         user1 = factories.user.create(xid=ctx.author_id, game=game)
#         user2 = factories.user.create(game=game)
#         factories.play.create(user_xid=user1.xid, game_id=game.id, points=0)
#         factories.play.create(user_xid=user2.xid, game_id=game.id, points=0)

#         message = MagicMock()
#         message.id = game.message_xid
#         message.edit = AsyncMock()

#         ctx.selected_options = [5]
#         ctx.defer = AsyncMock()
#         ctx.origin_message = message
#         cog = LookingForGameCog(bot)
#         await cog.points.func(cog, ctx)

#         found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
#         assert found.points == 5
#         assert message.edit.call_args_list[0].kwargs["embed"].to_dict() == {
#             "color": settings.EMBED_COLOR,
#             "description": (
#                 "Please check your Direct Messages for your SpellTable link.\n\n"
#                 "When your game is over use the drop down to report your points.\n\n"
#                 f"{guild.motd}\n\n{channel.motd}"
#             ),
#             "fields": [
#                 {
#                     "inline": False,
#                     "name": "Players",
#                     "value": f"<@{user1.xid}> (5 points), <@{user2.xid}>",
#                 },
#                 {"inline": True, "name": "Format", "value": "Commander"},
#             ],
#             "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#             "thumbnail": {"url": settings.THUMB_URL},
#             "title": "**Your game is ready!**",
#             "type": "rich",
#         }

#     async def test_points_when_message_not_found(
#         self,
#         bot: SpellBot,
#         ctx: ComponentContext,
#         factories: Factories,
#     ):
#         guild = factories.guild.create(xid=ctx.guild_id, show_points=True)
#         channel = factories.channel.create(xid=ctx.channel_id, guild=guild)
#         game = factories.game.create(
#             guild=guild,
#             channel=channel,
#             seats=2,
#             status=GameStatus.STARTED.value,
#             message_xid=12345,
#         )
#         user1 = factories.user.create(xid=ctx.author_id, game=game)
#         user2 = factories.user.create(game=game)
#         factories.play.create(user_xid=user1.xid, game_id=game.id, points=0)
#         factories.play.create(user_xid=user2.xid, game_id=game.id, points=0)

#         message = MagicMock()
#         message.id = game.message_xid + 10  # +10 so that it won't be found
#         message.edit = AsyncMock()

#         ctx.selected_options = [5]
#         ctx.defer = AsyncMock()
#         ctx.origin_message = message
#         cog = LookingForGameCog(bot)
#         await cog.points.func(cog, ctx)

#         found = DatabaseSession.query(Play).filter(Play.user_xid == user1.xid).one()
#         assert found.points == 0  # hasn't changed

#     async def test_points_when_not_in_game(
#         self,
#         bot: SpellBot,
#         ctx: ComponentContext,
#         factories: Factories,
#     ):
#         guild = factories.guild.create(xid=ctx.guild_id, show_points=True)
#         channel = factories.channel.create(xid=ctx.channel_id, guild=guild)
#         game = factories.game.create(
#             guild=guild,
#             channel=channel,
#             seats=2,
#             status=GameStatus.STARTED.value,
#             message_xid=12345,
#         )
#         user1 = factories.user.create(xid=ctx.author_id)
#         user2 = factories.user.create(game=game)
#         factories.play.create(user_xid=user2.xid, game_id=game.id, points=0)

#         message = MagicMock()
#         message.id = game.message_xid
#         message.edit = AsyncMock()

#         ctx.selected_options = [5]
#         ctx.defer = AsyncMock()
#         ctx.origin_message = message

#         player1 = mock_discord_user(user1)
#         player2 = mock_discord_user(user2)

#         with mock_operations(lfg_action, users=[player1, player2]):
#             cog = LookingForGameCog(bot)
#             await cog.points.func(cog, ctx)

#             lfg_action.safe_send_user.assert_called_once_with(
#                 ctx.author,
#                 "You are not one of the players in this game.",
#             )
