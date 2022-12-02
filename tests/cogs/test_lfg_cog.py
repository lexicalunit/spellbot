from __future__ import annotations

from typing import Callable
from unittest.mock import MagicMock

import discord
import pytest
from spellbot.actions import lfg_action
from spellbot.client import SpellBot
from spellbot.cogs import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, User

from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations


@pytest.fixture
def cog(bot: SpellBot) -> LookingForGameCog:
    return LookingForGameCog(bot)


@pytest.mark.asyncio
class TestCogLookingForGame(InteractionMixin):
    async def test_lfg(self, cog: LookingForGameCog, channel: Channel):
        await self.run(cog.lfg)
        game = DatabaseSession.query(Game).one()
        user = DatabaseSession.query(User).one()
        assert game.channel_xid == channel.xid
        assert game.guild_xid == self.guild.xid
        assert user.game_id == game.id

    async def test_lfg_fully_seated(
        self,
        cog: LookingForGameCog,
        add_channel: Callable[..., Channel],
    ):
        channel = add_channel(default_seats=2, xid=self.interaction.channel_id)
        game = self.factories.game.create(
            guild=self.guild,
            channel=channel,
            seats=2,
            message_xid=123,
        )
        other_user = self.factories.user.create(xid=self.interaction.user.id + 1, game=game)
        other_player = mock_discord_object(other_user)

        with mock_operations(lfg_action, users=[other_player]):
            message = MagicMock(spec=discord.Message)
            message.id = game.message_xid
            lfg_action.safe_get_partial_message.return_value = message

            await self.run(cog.lfg)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_action.safe_update_embed
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": self.settings.EMBED_COLOR,
                "description": (
                    "Please check your Direct Messages for your SpellTable link.\n\n"
                    f"{self.guild.motd}\n\n{channel.motd}"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"<@{self.interaction.user.id}>, <@{other_player.id}>",
                    },
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {
                        "inline": True,
                        "name": "Started at",
                        "value": f"<t:{game.started_at_timestamp}>",
                    },
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
                "thumbnail": {"url": self.settings.THUMB_URL},
                "title": "**Your game is ready!**",
                "type": "rich",
            }


# TODO
#     async def test_lfg_when_blocked(self):
#         guild = self.factories.guild.create(xid=self.ctx.guild_id)
#         channel = self.factories.channel.create(xid=self.ctx.channel_id, guild=guild)
#         author_user = self.factories.user.create(xid=self.ctx.author_id)
#         game = self.factories.game.create(guild=guild, channel=channel)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         self.factories.block.create(
#             user_xid=other_user.xid,
#             blocked_user_xid=author_user.xid,
#         )

#         cog = LookingForGameCog(self.bot)
#         await cog.lfg.func(cog, self.ctx)
#         other_game = DatabaseSession.query(Game).filter(Game.id == game.id).one_or_none()
#         assert other_game
#         author_game = DatabaseSession.query(Game).filter(Game.id != game.id).one_or_none()
#         assert author_game
#         assert other_game != author_game

#     async def test_lfg_when_already_in_game(self):
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         user = ctx_user(self.ctx, game=game)
#         author = mock_discord_user(user)

#         with mock_operations(lfg_action, users=[author]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)
#             lfg_action.safe_send_channel.assert_called_once_with(
#                 self.ctx,
#                 "You're already in a game.",
#             )

#         found = DatabaseSession.query(User).one()
#         assert found.game_id == game.id

#     async def test_lfg_with_format(self):
#         cog = LookingForGameCog(self.bot)
#         await cog.lfg.func(cog, self.ctx, format=GameFormat.MODERN.value)
#         assert DatabaseSession.query(Game).one().format == GameFormat.MODERN.value

#     async def test_lfg_with_seats(self):
#         cog = LookingForGameCog(self.bot)
#         await cog.lfg.func(cog, self.ctx, seats=2)
#         assert DatabaseSession.query(Game).one().seats == 2

#     async def test_lfg_with_friends(self):
#         assert self.ctx.guild
#         assert self.ctx.channel
#         assert isinstance(self.ctx.channel, discord.TextChannel)
#         assert isinstance(self.ctx.author, discord.User)
#         friend1 = build_author(10)
#         friend2 = build_author(20)
#         game_post = build_message(self.ctx.guild, self.ctx.channel, self.ctx.author)

#         with mock_operations(lfg_action, users=[self.ctx.author, friend1, friend2]):
#             lfg_action.safe_send_channel.return_value = game_post

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx, friends=f"<@{friend1.id}><@{friend2.id}>")

#         DatabaseSession.expire_all()
#         game = DatabaseSession.query(Game).one()
#         users = DatabaseSession.query(User).all()
#         assert len(users) == 3
#         for user in users:
#             assert user.game_id == game.id

#     async def test_lfg_with_too_many_friends(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         friend1 = build_author(10)
#         friend2 = build_author(20)
#         friend3 = build_author(30)
#         friend4 = build_author(40)

#         with mock_operations(
#             lfg_action,
#             users=[self.ctx.author, friend1, friend2, friend3, friend4],
#         ):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(
#                 cog,
#                 self.ctx,
#                 friends=f"<@{friend1.id}><@{friend2.id}><@{friend3.id}><@{friend4.id}>",
#             )

#         assert not DatabaseSession.query(Game).one_or_none()

#     async def test_lfg_when_initial_post_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_send_channel.return_value = None

#             post = MagicMock(spec=discord.Message)
#             post.id = 12345
#             lfg_action.safe_channel_reply.return_value = post

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_channel_reply
#             mock_call.assert_called_once()
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     "**A temporary issue prevented buttons from being added to this game"
#                     " post. To join or leave this game use `/lfg` or `/leave`.**\n\n"
#                     "_A SpellTable link will be created when all players have joined._"
#                 ),
#                 "fields": [
#                     {
#                         "inline": False,
#                         "name": "Players",
#                         "value": f"<@{self.ctx.author_id}>",
#                     },
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 3 more players to join...**",
#                 "type": "rich",
#             }

#     async def test_lfg_when_initial_post_and_reply_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_send_channel.return_value = None
#             lfg_action.safe_channel_reply.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_channel.assert_called_once()
#             lfg_action.safe_channel_reply.assert_called_once()
#             game = DatabaseSession.query(Game).one()
#             assert game.message_xid is None


# @pytest.mark.asyncio
# class TestCogLookingForGameCrossContext(BaseMixin):
#     # TODO: Refactor.
#     @pytest.mark.skip(reason="needs refactoring")
#     async def test_lfg_when_game_has_no_message_xid(self, guild: Guild, channel: Channel):
#         cog = LookingForGameCog(self.bot)
#         discord_guild = mock_discord_guild(guild)
#         discord_channel = mock_discord_channel(channel, guild=discord_guild)
#         player1 = mock_discord_user(self.factories.user.create())
#         player2 = mock_discord_user(self.factories.user.create())
#         ctx1 = build_ctx(discord_guild, discord_channel, player1, 1)
#         ctx2 = build_ctx(discord_guild, discord_channel, player2, 2)

#         with mock_operations(lfg_action, users=[player1, player2]):
#             # initial game post creation
#             lfg_action.safe_send_channel.return_value = build_message(
#                 discord_guild,
#                 discord_channel,
#                 build_client_user(),
#                 1,
#             )
#             await cog.lfg.func(cog, ctx1)
#             message_xid1 = DatabaseSession.query(Game.message_xid).scalar()

#             # simulate the game having a missing message_xid
#             DatabaseSession.execute(update(Game).values(message_xid=None))
#             DatabaseSession.commit()

#             # repost game post
#             lfg_action.safe_send_channel.return_value = build_message(
#                 discord_guild,
#                 discord_channel,
#                 build_client_user(),
#                 2,
#             )
#             await cog.lfg.func(cog, ctx2)
#             message_xid2 = DatabaseSession.query(Game.message_xid).scalar()

#             assert message_xid1 != message_xid2

#     # TODO: Refactor.
#     @pytest.mark.skip(reason="needs refactoring")
#     async def test_lfg_when_repost_game_fails(self, guild: Guild, channel: Channel):
#         cog = LookingForGameCog(self.bot)
#         discord_guild = mock_discord_guild(guild)
#         discord_channel = mock_discord_channel(channel, guild=discord_guild)
#         player1 = mock_discord_user(self.factories.user.create())
#         player2 = mock_discord_user(self.factories.user.create())
#         ctx1 = build_ctx(discord_guild, discord_channel, player1, 1)
#         ctx2 = build_ctx(discord_guild, discord_channel, player2, 2)

#         with mock_operations(lfg_action, users=[player1, player2]):
#             # initial game post creation
#             lfg_action.safe_send_channel.return_value = build_message(
#                 discord_guild,
#                 discord_channel,
#                 build_client_user(),
#                 1,
#             )
#             await cog.lfg.func(cog, ctx1)
#             message_xid1 = DatabaseSession.query(Game.message_xid).scalar()

#             # simulate the game having a missing message_xid
#             DatabaseSession.execute(update(Game).values(message_xid=None))
#             DatabaseSession.commit()

#             # repost game post
#             lfg_action.safe_send_channel.return_value = None
#             await cog.lfg.func(cog, ctx2)
#             message_xid2 = DatabaseSession.query(Game.message_xid).scalar()

#             assert message_xid1 != message_xid2
#             assert not message_xid2

#     async def test_lfg_multiple_times(self):
#         guild = build_guild()
#         channel = build_channel(guild=guild)
#         author1 = build_author(1)
#         author2 = build_author(2)
#         ctx1 = build_ctx(guild, channel, author1, 1)
#         ctx2 = build_ctx(guild, channel, author2, 2)
#         client_user = build_client_user()
#         game_post = build_message(guild, channel, client_user, 3)

#         cog = LookingForGameCog(self.bot)

#         with mock_operations(lfg_action, users=[author1, author2]):
#             lfg_action.safe_send_channel.return_value = game_post
#             await cog.lfg.func(cog, ctx1, seats=2)

#         with mock_operations(lfg_action, users=[author1, author2]):
#             await cog.lfg.func(cog, ctx2, seats=2)

#         game = DatabaseSession.query(Game).one()
#         assert game.to_dict() == {
#             "channel_xid": channel.id,
#             "created_at": game.created_at,
#             "deleted_at": None,
#             "format": game.format,
#             "guild_xid": guild.id,
#             "id": game.id,
#             "jump_link": game.jump_link,
#             "message_xid": game_post.id,
#             "seats": 2,
#             "spectate_link": game.spectate_link,
#             "spelltable_link": game.spelltable_link,
#             "started_at": game.started_at,
#             "status": GameStatus.STARTED.value,
#             "updated_at": game.updated_at,
#             "voice_invite_link": None,
#             "voice_xid": None,
#         }


# @pytest.mark.asyncio
# class TestCogLookingForGameJoinButton(ComponentContextMixin):
#     async def test_join(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild, motd=None)
#         game = ctx_game(self.ctx, guild, channel)
#         user = ctx_user(self.ctx)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             mock_call = lfg_action.safe_update_embed_origin
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     "_A SpellTable link will be created when all players have joined._\n"
#                     "\n"
#                     f"{guild.motd}"
#                 ),
#                 "fields": [
#                     {"inline": False, "name": "Players", "value": f"<@{user.xid}>"},
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 3 more players to join...**",
#                 "type": "rich",
#             }

#     async def test_join_with_show_points(self, snapshot: SnapshotAssertion):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, show_points=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             DatabaseSession.expire_all()
#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_update_embed_origin
#             mock_call.assert_called_once()
#             assert mock_call.call_args_list[0].kwargs["components"] == snapshot
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     "Please check your Direct Messages for your SpellTable link.\n\n"
#                     "When your game is over use the drop down to report your points.\n\n"
#                     f"{guild.motd}\n\n{channel.motd}"
#                 ),
#                 "fields": [
#                     {
#                         "inline": False,
#                         "name": "Players",
#                         "value": f"<@{self.ctx.author_id}>, <@{other_user.xid}>",
#                     },
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                     {
#                         "inline": True,
#                         "name": "Started at",
#                         "value": f"<t:{game.started_at_timestamp}>",
#                     },
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Your game is ready!**",
#                 "type": "rich",
#             }

#     async def test_join_when_blocked(self):
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         author_user = ctx_user(self.ctx)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)
#         self.factories.block.create(
#             user_xid=other_user.xid,
#             blocked_user_xid=author_user.xid,
#         )

#         with mock_operations(lfg_action, users=[author_user, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             mock_call = lfg_action.safe_send_user
#             mock_call.assert_called_once_with(
#                 self.ctx.author,
#                 "You can not join this game.",
#             )

#         assert DatabaseSession.query(Game).count() == 1

#     async def test_join_when_started(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         ctx_game(self.ctx, guild, channel, status=GameStatus.STARTED.value)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_called_once_with(
#                 self.ctx.author,
#                 "Sorry, that game has already started.",
#             )
#             lfg_action.safe_update_embed.assert_called_once_with(
#                 ANY,
#                 components=[],
#                 embed=ANY,
#             )

#     async def test_join_when_started_and_fetch_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         ctx_game(self.ctx, guild, channel, status=GameStatus.STARTED.value)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_called_once_with(
#                 self.ctx.author,
#                 "Sorry, that game has already started.",
#             )
#             lfg_action.safe_update_embed.assert_not_called()

#     async def test_join_when_update_embed_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         user = ctx_user(self.ctx)

#         with mock_operations(lfg_action, users=[self.ctx.author]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             lfg_action.safe_update_embed_origin.return_value = False

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#             mock_call = lfg_action.safe_update_embed_origin
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     "_A SpellTable link will be created when all players have joined._\n"
#                     "\n"
#                     f"{guild.motd}\n\n{channel.motd}"
#                 ),
#                 "fields": [
#                     {"inline": False, "name": "Players", "value": f"<@{user.xid}>"},
#                     {"inline": True, "name": "Format", "value": "Commander"},
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 3 more players to join...**",
#                 "type": "rich",
#             }


# @pytest.mark.asyncio
# class TestCogLookingForGameUserNotifications(InteractionContextMixin):
#     async def test_happy_path(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2, motd=None)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             DatabaseSession.expire_all()
#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_send_user
#             mock_call.assert_any_call(self.ctx.author, embed=ANY)
#             mock_call.assert_any_call(other_player, embed=ANY)
#             embed = mock_call.call_args_list[0].kwargs["embed"].to_dict()
#             assert embed == {
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     f"[Join your SpellTable game now!]({game.spelltable_link})"
#                     f" (or [spectate this game]({game.spectate_link}))\n\n"
#                     f"You can also [jump to the original game post]({game.jump_link}) in"
#                     f" <#{game.channel_xid}>."
#                 ),
#                 "fields": [
#                     {
#                         "inline": False,
#                         "name": "Players",
#                         "value": f"<@{self.ctx.author_id}>, <@{other_user.xid}>",
#                     },
#                     {"inline": True, "name": "Format", "value": game.format_name},
#                     {
#                         "inline": True,
#                         "name": "Started at",
#                         "value": f"<t:{game.started_at_timestamp}>",
#                     },
#                 ],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Your game is ready!**",
#                 "type": "rich",
#             }

#     async def test_lfg_when_mentioned_friend_is_blocked_by_current_player(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=4, motd=None)
#         game = ctx_game(self.ctx, guild, channel)
#         blocking_user = self.factories.user.create(
#             xid=self.ctx.author_id + 2,
#             game=game,
#         )
#         blocking_discord_user = mock_discord_user(blocking_user)

#         blocked_user = self.factories.user.create(xid=self.ctx.author_id + 1)
#         blocked_discord_user = mock_discord_user(blocked_user)

#         self.factories.block.create(
#             user_xid=blocking_user.xid,
#             blocked_user_xid=blocked_user.xid,
#         )

#         with mock_operations(
#             lfg_action,
#             users=[self.ctx.author, blocking_discord_user, blocked_discord_user],
#         ):
#             new_post = MagicMock(spec=discord.Message)
#             new_post.id = game.message_xid + 1
#             lfg_action.safe_send_channel.return_value = new_post

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx, friends=f"<@{blocked_user.xid}>")

#         DatabaseSession.expire_all()
#         assert DatabaseSession.query(Game).count() == 2
#         blocked_user = DatabaseSession.query(User).get(blocked_discord_user.id)
#         blocking_user = DatabaseSession.query(User).get(blocking_discord_user.id)
#         assert blocked_user and blocked_user.game_id is not None
#         assert blocking_user and blocking_user.game_id != blocked_user.game_id

#     async def test_when_fetch_user_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_fetch_user = AsyncMock(return_value=None)

#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_not_called()
#             # TODO: Refactor how this works.
#             # lfg_interaction.safe_send_channel.assert_any_call(
#             #     self.ctx,
#             #     (
#             #         "Unable to send Direct Messages to some players:"
#             #         f" <@!{other_player.id}>, <@!{self.ctx.author.id}>"
#             #     ),
#             # )


# @pytest.mark.asyncio
# class TestCogLookingForGameUserAwards(InteractionContextMixin):
#     async def test_happy_path(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)
#         guild_award = self.factories.guild_award.create(guild=guild, count=1)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_add_role.assert_any_call(
#                 self.ctx.author,
#                 self.ctx.guild,
#                 guild_award.role,
#                 False,
#             )
#             lfg_action.safe_add_role.assert_any_call(
#                 other_player,
#                 self.ctx.guild,
#                 guild_award.role,
#                 False,
#             )
#             lfg_action.safe_send_user.assert_any_call(
#                 self.ctx.author,
#                 guild_award.message,
#             )
#             lfg_action.safe_send_user.assert_any_call(
#                 other_player,
#                 guild_award.message,
#             )

#         awards = DatabaseSession.query(UserAward).all()
#         assert len(awards) == 2
#         for award in awards:
#             assert award.guild_award_id == guild_award.id

#     async def test_fetch_user_fails(self):
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         # other_player = \
#         mock_discord_user(other_user)
#         guild_award = self.factories.guild_award.create(guild=guild, count=1)

#         with mock_operations(lfg_action):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             # TODO: Refactor how this works.
#             # lfg_interaction.safe_send_channel.assert_any_call(
#             #     self.ctx,
#             #     (
#             #         f"Unable to give role {guild_award.role}"
#             #         f" to user <@{self.ctx.author_id}>"
#             #     ),
#             # )
#             # lfg_interaction.safe_send_channel.assert_any_call(
#             #     self.ctx,
#             #     f"Unable to give role {guild_award.role} to user <@{other_player.id}>",
#             # )
#             lfg_action.safe_add_role.assert_not_called()
#             lfg_action.safe_send_user.assert_not_called()

#         awards = DatabaseSession.query(UserAward).all()
#         assert len(awards) == 2
#         for award in awards:
#             assert award.guild_award_id == guild_award.id


# @pytest.mark.asyncio
# class TestCogLookingForGameWatchedUsers(InteractionContextMixin):
#     async def test_happy_path(self, monkeypatch):
#         assert self.ctx.guild
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2, motd=None)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)
#         watch = self.factories.watch.create(guild_xid=guild.xid, user_xid=other_user.xid)
#         db_mod = self.factories.user.create(xid=self.ctx.author_id + 2)
#         dpy_mod = mock_discord_user(db_mod)
#         mod_role = MagicMock(spec=discord.Role)
#         mod_role.name = self.settings.MOD_PREFIX
#         mod_role.members = [dpy_mod]
#         other_role = MagicMock(spec=discord.Role)
#         other_role.name = "nothing"
#         monkeypatch.setattr(self.ctx.guild, "roles", [other_role, mod_role])

#         with mock_operations(
#             lfg_action,
#             users=[
#                 self.ctx.author,
#                 other_player,
#                 dpy_mod,
#             ],
#         ):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             DatabaseSession.expire_all()
#             game = DatabaseSession.query(Game).one()
#             mock_call = lfg_action.safe_send_user
#             mock_call.assert_any_call(dpy_mod, embed=ANY)
#             assert mock_call.call_args_list[-1].kwargs["embed"].to_dict() == {
#                 "author": {"name": "Watched user(s) joined a game"},
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     f"[⇤ Jump to the game post]({game.jump_link})\n"
#                     f"[➤ Spectate the game on SpellTable]({game.spectate_link})\n\n"
#                     "**Users:**\n"
#                     f"• <@{other_player.id}>: {watch.note}"
#                 ),
#                 "thumbnail": {"url": self.settings.ICO_URL},
#                 "type": "rich",
#             }

#     async def test_when_no_mod_role(self, monkeypatch):
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         self.factories.watch.create(guild_xid=guild.xid, user_xid=other_user.xid)
#         db_mod = self.factories.user.create(xid=self.ctx.author_id + 2)
#         dpy_mod = mock_discord_user(db_mod)
#         monkeypatch.setattr(self.ctx.guild, "roles", [])

#         with mock_operations(lfg_action, users=[dpy_mod]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_not_called()

#     async def test_when_no_watched_users(self, monkeypatch):
#         guild = ctx_guild(self.ctx, motd=None, show_links=False)
#         channel = ctx_channel(self.ctx, guild, default_seats=2)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         self.factories.user.create(xid=self.ctx.author_id + 1, game=game)
#         db_mod = self.factories.user.create(xid=self.ctx.author_id + 2)
#         dpy_mod = mock_discord_user(db_mod)
#         mod_role = MagicMock(spec=discord.Role)
#         mod_role.name = self.settings.MOD_PREFIX
#         mod_role.members = [dpy_mod]
#         monkeypatch.setattr(self.ctx.guild, "roles", [mod_role])

#         with mock_operations(lfg_action, users=[dpy_mod]):
#             cog = LookingForGameCog(self.bot)
#             await cog.lfg.func(cog, self.ctx)

#             lfg_action.safe_send_user.assert_not_called()


# @pytest.mark.asyncio
# class TestCogLookingForGameLeaveButton(ComponentContextMixin):
#     async def test_leave(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel)
#         ctx_user(self.ctx, game=game)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             leave_action.safe_fetch_text_channel.return_value = self.ctx.channel
#             leave_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             mock_call = leave_action.safe_update_embed_origin
#             mock_call.assert_called_once()
#             assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
#                 "color": self.settings.EMBED_COLOR,
#                 "description": (
#                     "_A SpellTable link will be created when all players have joined._\n"
#                     "\n"
#                     f"{guild.motd}\n\n{channel.motd}"
#                 ),
#                 "fields": [{"inline": True, "name": "Format", "value": "Commander"}],
#                 "footer": {"text": f"SpellBot Game ID: #SB{game.id}"},
#                 "thumbnail": {"url": self.settings.THUMB_URL},
#                 "title": "**Waiting for 4 more players to join...**",
#                 "type": "rich",
#             }

#     async def test_leave_when_not_in_game(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         ctx_user(self.ctx)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             leave_action.safe_update_embed_origin.assert_not_called()
#             leave_action.safe_send_channel.assert_not_called()

#     async def test_leave_when_missing_game_post(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, message_xid=None)
#         ctx_user(self.ctx, game=game)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             leave_action.safe_update_embed_origin.assert_not_called()
#             leave_action.safe_send_channel.assert_not_called()

#     async def test_leave_message_mismatch(self):
#         assert self.ctx.message
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx)
#         channel = ctx_channel(self.ctx, guild)
#         wrong_message_xid = self.ctx.message.id + 1
#         game = ctx_game(self.ctx, guild, channel, seats=2, message_xid=wrong_message_xid)
#         ctx_user(self.ctx, xid=self.ctx.author_id, game=game)

#         with mock_operations(leave_action, users=[self.ctx.author]):
#             leave_action.safe_fetch_text_channel.return_value = self.ctx.channel
#             leave_action.safe_get_partial_message.return_value = self.ctx.message

#             cog = LookingForGameCog(self.bot)
#             await cog.leave.func(cog, self.ctx)

#             leave_action.safe_send_user.assert_called_once_with(
#                 self.ctx.author,
#                 "You're not in that game. Use the /leave command to leave a game.",
#             )


# @pytest.mark.asyncio
# class TestCogLookingForGameVoiceCreate(ComponentContextMixin):
#     async def test_join_happy_path(self):
#         assert self.ctx.guild
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             voice_channel = build_voice_channel(self.ctx.guild)
#             lfg_action.safe_create_voice_channel.return_value = voice_channel
#             lfg_action.safe_create_invite.return_value = "http://invite"

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert found.voice_xid == voice_channel.id
#         assert found.voice_invite_link == "http://invite"

#     async def test_join_when_category_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             lfg_action.safe_ensure_voice_category.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert not found.voice_xid
#         assert not found.voice_invite_link

#     async def test_join_when_channel_fails(self):
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             lfg_action.safe_create_voice_channel.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert not found.voice_xid
#         assert not found.voice_invite_link

#     async def test_join_when_invite_fails(self):
#         assert self.ctx.guild
#         assert self.ctx.author
#         assert isinstance(self.ctx.author, discord.User)
#         guild = ctx_guild(self.ctx, voice_create=True)
#         channel = ctx_channel(self.ctx, guild)
#         game = ctx_game(self.ctx, guild, channel, seats=2)
#         other_user = ctx_user(self.ctx, xid=self.ctx.author_id + 1, game=game)
#         other_player = mock_discord_user(other_user)

#         with mock_operations(lfg_action, users=[self.ctx.author, other_player]):
#             lfg_action.safe_get_partial_message.return_value = self.ctx.message
#             voice_channel = build_voice_channel(self.ctx.guild)
#             lfg_action.safe_create_voice_channel.return_value = voice_channel
#             lfg_action.safe_create_invite.return_value = None

#             cog = LookingForGameCog(self.bot)
#             await cog.join.func(cog, self.ctx)

#         found = DatabaseSession.query(Game).one()
#         assert found.voice_xid == voice_channel.id
#         assert not found.voice_invite_link
