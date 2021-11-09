from unittest.mock import ANY, AsyncMock, MagicMock

import discord
import pytest
from discord_slash.context import ComponentContext, InteractionContext
from sqlalchemy.sql.expression import update
from syrupy.assertion import SnapshotAssertion

from spellbot import SpellBot
from spellbot.cogs.lfg import LookingForGameCog
from spellbot.database import DatabaseSession
from spellbot.interactions import leave_interaction, lfg_interaction
from spellbot.models import Channel, Game, GameFormat, GameStatus, Guild, User, UserAward
from spellbot.settings import Settings
from tests.fixtures import Factories
from tests.mocks import (
    build_author,
    build_channel,
    build_client_user,
    build_ctx,
    build_guild,
    build_message,
    build_voice_channel,
    ctx_channel,
    ctx_game,
    ctx_guild,
    ctx_user,
    mock_discord_channel,
    mock_discord_guild,
    mock_discord_user,
    mock_operations,
)


@pytest.mark.asyncio
class TestCogLookingForGame:
    async def test_lfg(self, bot: SpellBot, ctx: InteractionContext):
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx)
        game = DatabaseSession.query(Game).one()
        user = DatabaseSession.query(User).one()
        assert game.channel_xid == ctx.channel_id
        assert game.guild_xid == ctx.guild_id
        assert user.game_id == game.id

    async def test_lfg_fully_seated(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        guild = factories.guild.create(xid=ctx.guild_id)
        channel = factories.channel.create(
            xid=ctx.channel_id, guild=guild, default_seats=2
        )
        author_user = factories.user.create(xid=ctx.author_id)
        game = factories.game.create(
            guild=guild, channel=channel, seats=2, message_xid=123
        )
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        author_player = mock_discord_user(author_user)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[author_player, other_player]):
            message = MagicMock(spec=discord.Message)
            message.id = game.message_xid
            lfg_interaction.safe_fetch_message.return_value = message

            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_interaction.safe_update_embed
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
                "color": settings.EMBED_COLOR,
                "description": (
                    "Please check your Direct Messages for your SpellTable link.\n\n"
                    f"{guild.motd}"
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"<@{author_player.id}>, <@{other_player.id}>",
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

    async def test_lfg_when_game_is_missing_message_xid(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ):
        cog = LookingForGameCog(bot)
        discord_guild = mock_discord_guild(guild)
        discord_channel = mock_discord_channel(channel, guild=discord_guild)
        client_user = build_client_user()
        game_post1 = build_message(discord_guild, discord_channel, client_user, 1)
        game_post2 = build_message(discord_guild, discord_channel, client_user, 2)
        user1 = factories.user.create()
        user2 = factories.user.create()
        player1 = mock_discord_user(user1)
        player2 = mock_discord_user(user2)
        ctx1 = build_ctx(discord_guild, discord_channel, player1, 1)
        ctx2 = build_ctx(discord_guild, discord_channel, player2, 2)

        with mock_operations(lfg_interaction, users=[player1, player2]):
            # initial game post creation
            lfg_interaction.safe_send_channel.return_value = game_post1
            await cog.lfg.func(cog, ctx1)
            message_xid1 = DatabaseSession.query(Game.message_xid).scalar()

            # simulate the game having a missing message_xid
            DatabaseSession.execute(update(Game).values(message_xid=None))
            DatabaseSession.commit()

            # repost game post
            lfg_interaction.safe_send_channel.return_value = game_post2
            await cog.lfg.func(cog, ctx2)
            message_xid2 = DatabaseSession.query(Game.message_xid).scalar()

            assert message_xid1 != message_xid2

    async def test_lfg_when_repost_game_fails(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ):
        cog = LookingForGameCog(bot)
        discord_guild = mock_discord_guild(guild)
        discord_channel = mock_discord_channel(channel, guild=discord_guild)
        client_user = build_client_user()
        game_post1 = build_message(discord_guild, discord_channel, client_user, 1)
        user1 = factories.user.create()
        user2 = factories.user.create()
        player1 = mock_discord_user(user1)
        player2 = mock_discord_user(user2)
        ctx1 = build_ctx(discord_guild, discord_channel, player1, 1)
        ctx2 = build_ctx(discord_guild, discord_channel, player2, 2)

        with mock_operations(lfg_interaction, users=[player1, player2]):
            # initial game post creation
            lfg_interaction.safe_send_channel.return_value = game_post1
            await cog.lfg.func(cog, ctx1)
            message_xid1 = DatabaseSession.query(Game.message_xid).scalar()

            # simulate the game having a missing message_xid
            DatabaseSession.execute(update(Game).values(message_xid=None))
            DatabaseSession.commit()

            # repost game post
            lfg_interaction.safe_send_channel.return_value = None
            await cog.lfg.func(cog, ctx2)
            message_xid2 = DatabaseSession.query(Game.message_xid).scalar()

            assert message_xid1 != message_xid2
            assert not message_xid2

    async def test_lfg_when_initial_post_fails(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        user = factories.user.create(xid=ctx.author_id)

        with mock_operations(lfg_interaction, users=[user]):
            lfg_interaction.safe_send_channel.return_value = None

            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

        game = DatabaseSession.query(Game).one()
        assert game.message_xid == None

    async def test_lfg_when_fetch_post_fails(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        guild = factories.guild.create(xid=ctx.guild_id)
        channel = factories.channel.create(xid=ctx.channel_id, guild=guild)
        user = factories.user.create(xid=ctx.author_id)
        other = factories.user.create(xid=ctx.author_id + 1)
        game = factories.game.create(guild=guild, channel=channel, message_xid=100)

        with mock_operations(lfg_interaction, users=[user, other]):
            lfg_interaction.safe_fetch_message.return_value = None

            message = MagicMock(spec=discord.Message)
            message.id = game.message_xid + 1
            lfg_interaction.safe_send_channel.return_value = message

            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            lfg_interaction.safe_send_channel.assert_called_once()

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        assert game.message_xid == 101

    async def test_lfg_when_blocked(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        guild = factories.guild.create(xid=ctx.guild_id)
        channel = factories.channel.create(xid=ctx.channel_id, guild=guild)
        author_user = factories.user.create(xid=ctx.author_id)
        game = factories.game.create(guild=guild, channel=channel)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=author_user.xid)

        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx)
        other_game = DatabaseSession.query(Game).filter(Game.id == game.id).one_or_none()
        assert other_game
        author_game = DatabaseSession.query(Game).filter(Game.id != game.id).one_or_none()
        assert author_game
        assert other_game != author_game

    async def test_lfg_when_already_in_game(self, bot: SpellBot, ctx: InteractionContext):
        guild = ctx_guild(ctx)
        channel = ctx_channel(ctx, guild)
        game = ctx_game(ctx, guild, channel)
        ctx_user(ctx, game=game)
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx)
        found = DatabaseSession.query(User).one()
        assert found.game_id == game.id
        ctx.send.assert_called_once_with("You're already in a game.", hidden=True)

    async def test_lfg_with_format(self, bot: SpellBot, ctx: InteractionContext):
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx, format=GameFormat.MODERN.value)
        assert DatabaseSession.query(Game).one().format == GameFormat.MODERN.value

    async def test_lfg_with_seats(self, bot: SpellBot, ctx: InteractionContext):
        cog = LookingForGameCog(bot)
        await cog.lfg.func(cog, ctx, seats=2)
        assert DatabaseSession.query(Game).one().seats == 2

    async def test_lfg_with_friends(self, bot: SpellBot, ctx: InteractionContext):
        assert ctx.guild
        assert ctx.channel
        assert isinstance(ctx.channel, discord.TextChannel)
        assert isinstance(ctx.author, discord.User)
        friend1 = build_author(10)
        friend2 = build_author(20)
        game_post = build_message(ctx.guild, ctx.channel, ctx.author)

        with mock_operations(lfg_interaction, users=[ctx.author, friend1, friend2]):
            lfg_interaction.safe_send_channel.return_value = game_post

            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx, friends=f"<@{friend1.id}><@{friend2.id}>")

        DatabaseSession.expire_all()
        game = DatabaseSession.query(Game).one()
        users = DatabaseSession.query(User).all()
        assert len(users) == 3
        for user in users:
            assert user.game_id == game.id

    async def test_lfg_with_too_many_friends(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
    ):
        assert ctx.author
        assert isinstance(ctx.author, discord.User)
        friend1 = build_author(10)
        friend2 = build_author(20)
        friend3 = build_author(30)
        friend4 = build_author(40)

        with mock_operations(
            lfg_interaction,
            users=[ctx.author, friend1, friend2, friend3, friend4],
        ):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(
                cog,
                ctx,
                friends=f"<@{friend1.id}><@{friend2.id}><@{friend3.id}><@{friend4.id}>",
            )

        assert not DatabaseSession.query(Game).one_or_none()

    async def test_lfg_multiple_times(self, bot: SpellBot):
        guild = build_guild()
        channel = build_channel(guild=guild)
        author1 = build_author(1)
        author2 = build_author(2)
        ctx1 = build_ctx(guild, channel, author1, 1)
        ctx2 = build_ctx(guild, channel, author2, 2)
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
    async def test_join(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
        settings: Settings,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel)
        user = ctx_user(origin_ctx)

        with mock_operations(lfg_interaction, users=[origin_ctx.author]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

            mock_call = lfg_interaction.safe_update_embed_origin
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
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

    async def test_join_with_show_points(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
        settings: Settings,
        factories: Factories,
        snapshot: SnapshotAssertion,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx, show_points=True)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=origin_ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[origin_ctx.author, other_player]):
            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_interaction.safe_update_embed_origin
            mock_call.assert_called_once()
            assert mock_call.call_args_list[0].kwargs["components"] == snapshot
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
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
                        "value": f"<@{origin_ctx.author_id}>, <@{other_user.xid}>",
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

    async def test_join_when_blocked(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
        factories: Factories,
    ):
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel)
        author_user = ctx_user(origin_ctx)
        other_user = factories.user.create(xid=origin_ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)
        factories.block.create(user_xid=other_user.xid, blocked_user_xid=author_user.xid)

        with mock_operations(lfg_interaction, users=[author_user, other_player]):
            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

            mock_call = lfg_interaction.safe_send_channel
            mock_call.assert_called_once_with(
                origin_ctx,
                "You can not join this game.",
                hidden=True,
            )

        assert DatabaseSession.query(Game).count() == 1

    async def test_join_when_started(self, bot: SpellBot, origin_ctx: ComponentContext):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        ctx_game(origin_ctx, guild, channel, status=GameStatus.STARTED.value)

        with mock_operations(lfg_interaction, users=[origin_ctx.author]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

            lfg_interaction.safe_send_channel.assert_called_once_with(
                origin_ctx,
                "Sorry, that game has already started.",
                hidden=True,
            )
            lfg_interaction.safe_update_embed.assert_called_once_with(
                ANY,
                components=[],
                embed=ANY,
            )

    async def test_join_when_started_and_fetch_fails(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        ctx_game(origin_ctx, guild, channel, status=GameStatus.STARTED.value)

        with mock_operations(lfg_interaction, users=[origin_ctx.author]):
            lfg_interaction.safe_fetch_message.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

            lfg_interaction.safe_send_channel.assert_called_once_with(
                origin_ctx,
                "Sorry, that game has already started.",
                hidden=True,
            )
            lfg_interaction.safe_update_embed.assert_not_called()

    async def test_join_when_update_embed_fails(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
        settings: Settings,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel)
        user = ctx_user(origin_ctx)

        with mock_operations(lfg_interaction, users=[origin_ctx.author]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message
            lfg_interaction.safe_update_embed_origin.return_value = False

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

            mock_call = lfg_interaction.safe_update_embed
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
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


@pytest.mark.asyncio
class TestCogLookingForGameUserNotifications:
    async def test_happy_path(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
    ):
        assert ctx.author
        assert isinstance(ctx.author, discord.User)
        guild = ctx_guild(ctx, motd=None, show_links=False)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_interaction.safe_send_user
            mock_call.assert_any_call(ctx.author, embed=ANY)
            mock_call.assert_any_call(other_player, embed=ANY)
            embed = mock_call.call_args_list[0].kwargs["embed"].to_dict()
            assert embed == {
                "color": settings.EMBED_COLOR,
                "description": (
                    f"[Join your SpellTable game now!]({game.spelltable_link})"
                    f" (or [spectate this game]({game.spectate_link}))\n\n"
                    f"You can also [jump to the original game post]({game.jump_link}) in"
                    f" <#{game.channel_xid}>."
                ),
                "fields": [
                    {
                        "inline": False,
                        "name": "Players",
                        "value": f"<@{ctx.author_id}>, <@{other_user.xid}>",
                    },
                    {"inline": True, "name": "Format", "value": game.format_name},
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

    async def test_when_fetch_user_fails(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        assert ctx.author
        assert isinstance(ctx.author, discord.User)
        guild = ctx_guild(ctx)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            lfg_interaction.safe_fetch_user = AsyncMock(return_value=None)

            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            lfg_interaction.safe_send_user.assert_not_called()
            lfg_interaction.safe_send_channel.assert_any_call(
                ctx,
                (
                    "Unable to send Direct Messages to some players:"
                    f" <@!{other_player.id}>, <@!{ctx.author.id}>"
                ),
            )


@pytest.mark.asyncio
class TestCogLookingForGameUserAwards:
    async def test_happy_path(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        assert ctx.author
        assert isinstance(ctx.author, discord.User)
        guild = ctx_guild(ctx, motd=None, show_links=False)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)
        guild_award = factories.guild_award.create(guild=guild, count=1)

        with mock_operations(lfg_interaction, users=[ctx.author, other_player]):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            lfg_interaction.safe_add_role.assert_any_call(
                ctx.author,
                ctx.guild,
                guild_award.role,
            )
            lfg_interaction.safe_add_role.assert_any_call(
                other_player,
                ctx.guild,
                guild_award.role,
            )
            lfg_interaction.safe_send_user.assert_any_call(
                ctx.author,
                guild_award.message,
            )
            lfg_interaction.safe_send_user.assert_any_call(
                other_player,
                guild_award.message,
            )

        awards = DatabaseSession.query(UserAward).all()
        assert len(awards) == 2
        for award in awards:
            assert award.guild_award_id == guild_award.id

    async def test_fetch_user_fails(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
    ):
        guild = ctx_guild(ctx, motd=None, show_links=False)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)
        guild_award = factories.guild_award.create(guild=guild, count=1)

        with mock_operations(lfg_interaction):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            lfg_interaction.safe_send_channel.assert_any_call(
                ctx,
                f"Unable to give role {guild_award.role} to user <@{ctx.author_id}>",
            )
            lfg_interaction.safe_send_channel.assert_any_call(
                ctx,
                f"Unable to give role {guild_award.role} to user <@{other_player.id}>",
            )
            lfg_interaction.safe_add_role.assert_not_called()
            lfg_interaction.safe_send_user.assert_not_called()

        awards = DatabaseSession.query(UserAward).all()
        assert len(awards) == 2
        for award in awards:
            assert award.guild_award_id == guild_award.id


@pytest.mark.asyncio
class TestCogLookingForGameWatchedUsers:
    async def test_happy_path(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
        monkeypatch,
    ):
        assert ctx.guild
        assert ctx.author
        assert isinstance(ctx.author, discord.User)
        guild = ctx_guild(ctx, motd=None, show_links=False)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)
        watch = factories.watch.create(guild_xid=guild.xid, user_xid=other_user.xid)
        db_mod = factories.user.create(xid=ctx.author_id + 2)
        dpy_mod = mock_discord_user(db_mod)
        mod_role = MagicMock(spec=discord.Role)
        mod_role.name = settings.MOD_PREFIX
        mod_role.members = [dpy_mod]
        other_role = MagicMock(spec=discord.Role)
        other_role.name = "nothing"
        monkeypatch.setattr(ctx.guild, "roles", [other_role, mod_role])

        with mock_operations(lfg_interaction, users=[ctx.author, other_player, dpy_mod]):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            DatabaseSession.expire_all()
            game = DatabaseSession.query(Game).one()
            mock_call = lfg_interaction.safe_send_user
            mock_call.assert_any_call(dpy_mod, embed=ANY)
            assert mock_call.call_args_list[-1].kwargs["embed"].to_dict() == {
                "author": {"name": "Watched user(s) joined a game"},
                "color": settings.EMBED_COLOR,
                "description": (
                    f"[⇤ Jump to the game post]({game.jump_link})\n"
                    f"[➤ Spectate the game on SpellTable]({game.spectate_link})\n\n"
                    "**Users:**\n"
                    f"• <@{other_player.id}>: {watch.note}"
                ),
                "thumbnail": {"url": settings.ICO_URL},
                "type": "rich",
            }

    async def test_when_no_mod_role(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        factories: Factories,
        monkeypatch,
    ):
        guild = ctx_guild(ctx, motd=None, show_links=False)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        other_user = factories.user.create(xid=ctx.author_id + 1, game=game)
        factories.watch.create(guild_xid=guild.xid, user_xid=other_user.xid)
        db_mod = factories.user.create(xid=ctx.author_id + 2)
        dpy_mod = mock_discord_user(db_mod)
        monkeypatch.setattr(ctx.guild, "roles", [])

        with mock_operations(lfg_interaction, users=[dpy_mod]):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            lfg_interaction.safe_send_user.assert_not_called()

    async def test_when_no_watched_users(
        self,
        bot: SpellBot,
        ctx: InteractionContext,
        settings: Settings,
        factories: Factories,
        monkeypatch,
    ):
        guild = ctx_guild(ctx, motd=None, show_links=False)
        channel = ctx_channel(ctx, guild, default_seats=2)
        game = ctx_game(ctx, guild, channel, seats=2)
        factories.user.create(xid=ctx.author_id + 1, game=game)
        db_mod = factories.user.create(xid=ctx.author_id + 2)
        dpy_mod = mock_discord_user(db_mod)
        mod_role = MagicMock(spec=discord.Role)
        mod_role.name = settings.MOD_PREFIX
        mod_role.members = [dpy_mod]
        monkeypatch.setattr(ctx.guild, "roles", [mod_role])

        with mock_operations(lfg_interaction, users=[dpy_mod]):
            cog = LookingForGameCog(bot)
            await cog.lfg.func(cog, ctx)

            lfg_interaction.safe_send_user.assert_not_called()


@pytest.mark.asyncio
class TestCogLookingForGameLeaveButton:
    async def test_leave(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
        settings: Settings,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel)
        ctx_user(origin_ctx, game=game)

        with mock_operations(leave_interaction, users=[origin_ctx.author]):
            leave_interaction.safe_fetch_text_channel.return_value = origin_ctx.channel
            leave_interaction.safe_fetch_message.return_value = origin_ctx.message

            cog = LookingForGameCog(bot)
            await cog.leave.func(cog, origin_ctx)

            mock_call = leave_interaction.safe_update_embed_origin
            mock_call.assert_called_once()
            assert mock_call.call_args_list[0].kwargs["embed"].to_dict() == {
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

    async def test_leave_message_mismatch(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
    ):
        assert origin_ctx.message
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx)
        channel = ctx_channel(origin_ctx, guild)
        wrong_message_xid = origin_ctx.message.id + 1
        game = ctx_game(
            origin_ctx, guild, channel, seats=2, message_xid=wrong_message_xid
        )
        ctx_user(origin_ctx, xid=origin_ctx.author_id, game=game)

        with mock_operations(leave_interaction, users=[origin_ctx.author]):
            leave_interaction.safe_fetch_text_channel.return_value = origin_ctx.channel
            leave_interaction.safe_fetch_message.return_value = origin_ctx.message

            cog = LookingForGameCog(bot)
            await cog.leave.func(cog, origin_ctx)

            leave_interaction.safe_send_channel.assert_called_once_with(
                origin_ctx,
                "You have been removed from any games your were signed up for.",
                hidden=True,
            )


@pytest.mark.asyncio
class TestCogLookingForGameVoiceCreate:
    async def test_join_happy_path(self, bot: SpellBot, origin_ctx: ComponentContext):
        assert origin_ctx.guild
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx, voice_create=True)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel, seats=2)
        other_user = ctx_user(origin_ctx, xid=origin_ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[origin_ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message
            voice_channel = build_voice_channel(origin_ctx.guild)
            lfg_interaction.safe_create_voice_channel.return_value = voice_channel
            lfg_interaction.safe_create_invite.return_value = "http://invite"

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

        found = DatabaseSession.query(Game).one()
        assert found.voice_xid == voice_channel.id
        assert found.voice_invite_link == "http://invite"

    async def test_join_when_category_fails(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx, voice_create=True)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel, seats=2)
        other_user = ctx_user(origin_ctx, xid=origin_ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[origin_ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message
            lfg_interaction.safe_ensure_voice_category.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

        found = DatabaseSession.query(Game).one()
        assert not found.voice_xid
        assert not found.voice_invite_link

    async def test_join_when_channel_fails(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
    ):
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx, voice_create=True)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel, seats=2)
        other_user = ctx_user(origin_ctx, xid=origin_ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[origin_ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message
            lfg_interaction.safe_create_voice_channel.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

        found = DatabaseSession.query(Game).one()
        assert not found.voice_xid
        assert not found.voice_invite_link

    async def test_join_when_invite_fails(
        self,
        bot: SpellBot,
        origin_ctx: ComponentContext,
    ):
        assert origin_ctx.guild
        assert origin_ctx.author
        assert isinstance(origin_ctx.author, discord.User)
        guild = ctx_guild(origin_ctx, voice_create=True)
        channel = ctx_channel(origin_ctx, guild)
        game = ctx_game(origin_ctx, guild, channel, seats=2)
        other_user = ctx_user(origin_ctx, xid=origin_ctx.author_id + 1, game=game)
        other_player = mock_discord_user(other_user)

        with mock_operations(lfg_interaction, users=[origin_ctx.author, other_player]):
            lfg_interaction.safe_fetch_message.return_value = origin_ctx.message
            voice_channel = build_voice_channel(origin_ctx.guild)
            lfg_interaction.safe_create_voice_channel.return_value = voice_channel
            lfg_interaction.safe_create_invite.return_value = None

            cog = LookingForGameCog(bot)
            await cog.join.func(cog, origin_ctx)

        found = DatabaseSession.query(Game).one()
        assert found.voice_xid == voice_channel.id
        assert not found.voice_invite_link
