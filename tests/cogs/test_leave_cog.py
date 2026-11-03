# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import ANY

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update

from spellbot.actions import leave_action
from spellbot.cogs import LeaveGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild, Post, Queue, User
from spellbot.settings import settings as runtime_settings
from spellbot.views.lfg_view import GameView
from tests.fixtures import Factories, run_command
from tests.mocks import mock_operations

if TYPE_CHECKING:
    import discord
    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.settings import Settings

pytestmark = pytest.mark.use_db

CONVOKE_PENDING_MSG = (
    "_A [Convoke](https://www.convoke.games/) link will be created when all players have joined._"
)


WAR_CONVOKE_ONLY = (
    "This Guild War table no longer takes players through SpellBot, "
    "but you can still join it on Convoke."
)
CONVOKE_TABLE = "https://www.convoke.games/table/1"


async def open_convoke_war_table(game: Game) -> None:
    await DatabaseSession.execute(
        update(Game)
        .where(Game.id == game.id)
        .values(war_id="war-a", war_title="War A", game_link=CONVOKE_TABLE),
    )
    await DatabaseSession.commit()


async def is_deleted(game: Game) -> bool:
    deleted_at = await DatabaseSession.scalar(select(Game.deleted_at).where(Game.id == game.id))
    return deleted_at is not None


def support_cta(guild_xid: int) -> str:
    return (
        f"\n\n-# You can view [live games]({runtime_settings.API_BASE_URL}/queues) "
        f"and [get notified]({runtime_settings.API_BASE_URL}/queues/g/{guild_xid}).\n"
        "-# **Support SpellBot** — "
        "Become [a patron](https://www.patreon.com/lexicalunit) "
        "or give a [one-off tip](https://ko-fi.com/lexicalunit)."
    )


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> LeaveGameCog:
    return LeaveGameCog(bot)


@pytest.mark.asyncio
class TestCogLeaveGame:
    async def test_leave(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_called_once()
            safe_update_embed_call = ops.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{CONVOKE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}")
                + support_cta(guild.xid),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_leave_then_delete(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_not_called()
            ops.safe_delete_message.assert_called_once_with(message, own_message=True)

    async def test_leave_all(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_called_once()
            safe_update_embed_call = ops.safe_update_embed.call_args_list[0]
            assert safe_update_embed_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{CONVOKE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}")
                + support_cta(guild.xid),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_leave_all_updates_every_post_by_its_own_message(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        other_channel = factories.channel.create(guild=guild)
        factories.post.create(guild=guild, channel=other_channel, game=game, message_xid=424242)
        await DatabaseSession.commit()
        post_xids = sorted(post.message_xid for post in game.posts)
        assert len(post_xids) == 2

        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            fetched = sorted(c.args[2] for c in ops.safe_get_partial_message.call_args_list)
            assert fetched == post_xids
            assert ops.safe_update_embed.call_count == 2

    async def test_leave_all_then_delete(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_not_called()
            ops.safe_delete_message.assert_called_once_with(message, own_message=True)

    async def test_leave_all_when_no_games(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_not_called()

    async def test_leave_all_when_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = None
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_all, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_not_called()

    async def test_leave_all_when_get_message_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = None

            await run_command(cog.leave_all, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from all pending games.",
                ephemeral=True,
            )
            ops.safe_update_embed.assert_not_called()

    async def test_leave_when_no_message_xid(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        channel: Channel,
    ) -> None:
        await DatabaseSession.execute(delete(Post).where(Post.game_id == game.id))
        await DatabaseSession.commit()

        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_not_in_game(
        self,
        cog: LeaveGameCog,
        user: User,
        interaction: discord.Interaction,
    ) -> None:
        with mock_operations(leave_action) as ops:
            await run_command(cog.leave_command, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_no_channel(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = None

            await run_command(cog.leave_command, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_when_no_message(
        self,
        cog: LeaveGameCog,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        channel: Channel,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = channel
            ops.safe_get_partial_message.return_value = None

            await run_command(cog.leave_command, interaction)

            ops.safe_send_channel.assert_called_once_with(
                interaction,
                "You were removed from any pending games in this channel.",
                ephemeral=True,
            )

    async def test_leave_button(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
        bot: SpellBot,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_called_once()
            safe_update_embed_origin_call = ops.safe_update_embed_origin.call_args_list[0]
            assert safe_update_embed_origin_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{CONVOKE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}")
                + support_cta(guild.xid),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

    async def test_leave_war_game_hands_post_to_convoke(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
    ) -> None:
        await open_convoke_war_table(game)
        with mock_operations(leave_action) as ops:
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message

            await run_command(cog.leave_command, interaction)

            ops.safe_delete_message.assert_not_called()
            ops.safe_update_embed.assert_called_once_with(
                message,
                content=WAR_CONVOKE_ONLY,
                embed=ANY,
                view=None,
            )
            embed = ops.safe_update_embed.call_args.kwargs["embed"]
            assert CONVOKE_TABLE in embed.description
        assert await is_deleted(game)

    async def test_leave_button_war_game_hands_post_to_convoke(
        self,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        await open_convoke_war_table(game)
        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_delete_message.assert_not_called()
            ops.safe_update_embed_origin.assert_called_once_with(
                interaction,
                content=WAR_CONVOKE_ONLY,
                embed=ANY,
                view=None,
            )
        assert await is_deleted(game)

    async def test_leave_button_then_delete(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()
            ops.safe_delete_message.assert_called_once_with(
                interaction.message,
                own_message=True,
            )

    async def test_leave_button_with_other_players(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
        bot: SpellBot,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_called_once_with(
                interaction,
                embed=ANY,
            )
            safe_update_embed_origin_call = ops.safe_update_embed_origin.call_args_list[0]
            assert safe_update_embed_origin_call.kwargs["embed"].to_dict() == {
                "color": settings.PENDING_EMBED_COLOR,
                "description": (f"{CONVOKE_PENDING_MSG}\n\n{guild.motd}\n\n{channel.motd}")
                + support_cta(guild.xid),
                "fields": [
                    {"inline": False, "name": "Players", "value": f"• <@{p2.xid}> ({p2.name})"},
                    {"inline": True, "name": "Format", "value": "Commander"},
                    {"inline": True, "name": "Updated at", "value": ANY},
                ],
                "footer": {"text": f"SpellBot Game ID: #SB{game.id} — Service: Convoke"},
                "thumbnail": {"url": settings.THUMB_URL},
                "title": "**Waiting for 3 more players to join...**",
                "type": "rich",
                "flags": 0,
            }

            ops.safe_delete_message.assert_not_called()

    async def test_leave_button_when_no_game(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
        interaction: discord.Interaction,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()

    async def test_leave_button_when_message_missing(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = None
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()
            ops.safe_delete_message.assert_called_once_with(message, own_message=True)

    async def test_leave_button_when_message_missing_with_other_players(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        factories: Factories,
    ) -> None:
        """Test leave button when original response doesn't match but other players remain."""
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = None
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()
            ops.safe_update_embed.assert_called_once()
            ops.safe_delete_message.assert_not_called()

    async def test_leave_button_when_message_missing_and_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = None
            ops.safe_fetch_text_channel.return_value = None
            ops.safe_get_partial_message.return_value = message
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()
            ops.safe_update_embed.assert_not_called()

    async def test_leave_button_when_message_missing_and_get_message_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
    ) -> None:
        with mock_operations(leave_action) as ops:
            ops.safe_original_response.return_value = None
            ops.safe_fetch_text_channel.return_value = interaction.channel
            ops.safe_get_partial_message.return_value = None
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()
            ops.safe_update_embed.assert_not_called()

    async def test_leave_button_when_defer_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch(
            "spellbot.views.lfg_view.safe_defer_interaction",
            return_value=False,
        )
        with mock_operations(leave_action) as ops:
            view = GameView(bot)

            await view.leave(interaction)

            ops.safe_update_embed_origin.assert_not_called()
            ops.safe_delete_message.assert_not_called()
