# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import pytest
import pytest_asyncio
from decoy import matchers
from sqlalchemy import delete, select, update

from spellbot import operations
from spellbot.actions import leave_action
from spellbot.cogs import LeaveGameCog
from spellbot.database import DatabaseSession
from spellbot.models import Channel, Game, Guild, Post, Queue, User
from spellbot.settings import settings as runtime_settings
from spellbot.views import lfg_view
from spellbot.views.lfg_view import GameView
from tests.fixtures import Factories, run_command
from tests.mocks import mock_operations
from tests.mocks.decoys import ANY, captured

if TYPE_CHECKING:
    from decoy import Decoy

    from spellbot import SpellBot
    from spellbot.settings import Settings
    from tests.fixtures import Stub

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
        "\n\n-# **Settings** — "
        f"See [live games]({runtime_settings.API_BASE_URL}/queues) and configure "
        f"[your notifications]({runtime_settings.API_BASE_URL}/queues/g/{guild_xid}).\n"
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
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
        decoy: Decoy,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from any pending games in this channel.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=1,
                ignore_extra_args=True,
            )
            safe_update_embed_embed = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed(ANY, embed=safe_update_embed_embed),
                ignore_extra_args=True,
            )
            assert captured(safe_update_embed_embed, discord.Embed).to_dict() == {
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
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from any pending games in this channel.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(await operations.safe_delete_message(message, own_message=True), times=1)

    async def test_leave_all(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
        decoy: Decoy,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_all, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from all pending games.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=1,
                ignore_extra_args=True,
            )
            safe_update_embed_embed = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed(ANY, embed=safe_update_embed_embed),
                ignore_extra_args=True,
            )
            assert captured(safe_update_embed_embed, discord.Embed).to_dict() == {
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
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        other_channel = factories.channel.create(guild=guild)
        factories.post.create(guild=guild, channel=other_channel, game=game, message_xid=424242)
        await DatabaseSession.commit()
        post_xids = sorted(post.message_xid for post in game.posts)
        assert len(post_xids) == 2

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_all, interaction)

            # Each post is fetched by its own message, once.
            for xid in post_xids:
                decoy.verify(operations.safe_get_partial_message(ANY, ANY, xid), times=1)
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=2,
                ignore_extra_args=True,
            )

    async def test_leave_all_then_delete(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_all, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from all pending games.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(await operations.safe_delete_message(message, own_message=True), times=1)

    async def test_leave_all_when_no_games(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_all, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from all pending games.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_all_when_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(None)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_all, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from all pending games.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_all_when_get_message_fails(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(None)

            await run_command(cog.leave_all, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from all pending games.",
                    ephemeral=True,
                ),
                times=1,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_when_no_message_xid(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        await DatabaseSession.execute(delete(Post).where(Post.game_id == game.id))
        await DatabaseSession.commit()

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from any pending games in this channel.",
                    ephemeral=True,
                ),
                times=1,
            )

    async def test_leave_when_not_in_game(
        self,
        cog: LeaveGameCog,
        user: User,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from any pending games in this channel.",
                    ephemeral=True,
                ),
                times=1,
            )

    async def test_leave_when_no_channel(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(None)

            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from any pending games in this channel.",
                    ephemeral=True,
                ),
                times=1,
            )

    async def test_leave_when_no_message(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(None)

            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_send_channel(
                    interaction,
                    "You were removed from any pending games in this channel.",
                    ephemeral=True,
                ),
                times=1,
            )

    async def test_leave_button(
        self,
        original_message: discord.InteractionMessage,
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
        decoy: Decoy,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(original_message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=1,
                ignore_extra_args=True,
            )
            safe_update_embed_origin_embed = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed_origin(
                    ANY,
                    embed=safe_update_embed_origin_embed,
                ),
                ignore_extra_args=True,
            )
            assert captured(safe_update_embed_origin_embed, discord.Embed).to_dict() == {
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
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        decoy: Decoy,
    ) -> None:
        await open_convoke_war_table(game)
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(cog.leave_command, interaction)

            decoy.verify(
                await operations.safe_delete_message(message=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_update_embed(
                    message,
                    content=WAR_CONVOKE_ONLY,
                    embed=ANY,
                    view=None,
                ),
                times=1,
            )
            safe_update_embed_embed = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed(ANY, embed=safe_update_embed_embed),
                ignore_extra_args=True,
            )
            embed = captured(safe_update_embed_embed, discord.Embed)
            assert embed.description
            assert CONVOKE_TABLE in embed.description
        assert await is_deleted(game)

    async def test_leave_button_war_game_hands_post_to_convoke(
        self,
        original_message: discord.InteractionMessage,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        await open_convoke_war_table(game)
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(original_message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_delete_message(message=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_update_embed_origin(
                    interaction,
                    content=WAR_CONVOKE_ONLY,
                    embed=ANY,
                    view=None,
                ),
                times=1,
            )
        assert await is_deleted(game)

    async def test_leave_button_then_delete(
        self,
        original_message: discord.InteractionMessage,
        cog: LeaveGameCog,
        message: discord.Message,
        game: Game,
        player: User,
        interaction: discord.Interaction,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(original_message)
            interaction.message = message
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_delete_message(message, own_message=True),
                times=1,
            )

    async def test_leave_button_with_other_players(
        self,
        original_message: discord.InteractionMessage,
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
        decoy: Decoy,
    ) -> None:
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(original_message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(await operations.safe_update_embed_origin(interaction, embed=ANY), times=1)
            safe_update_embed_origin_embed = matchers.ValueCaptor()
            decoy.verify(
                await operations.safe_update_embed_origin(
                    ANY,
                    embed=safe_update_embed_origin_embed,
                ),
                ignore_extra_args=True,
            )
            assert captured(safe_update_embed_origin_embed, discord.Embed).to_dict() == {
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

            decoy.verify(
                await operations.safe_delete_message(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_button_when_no_game(
        self,
        original_message: discord.InteractionMessage,
        cog: LeaveGameCog,
        message: discord.Message,
        user: User,
        interaction: discord.Interaction,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(original_message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_button_when_message_missing(
        self,
        decoy_channel: discord.TextChannel,
        original_message: discord.InteractionMessage,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(None)
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(await operations.safe_delete_message(message, own_message=True), times=1)

    async def test_leave_button_when_message_missing_with_other_players(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        """Test leave button when original response doesn't match but other players remain."""
        p2 = factories.user.create()
        DatabaseSession.add(Queue(user_xid=p2.xid, game_id=game.id, og_guild_xid=game.guild_xid))
        await DatabaseSession.commit()

        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(None)
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=1,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_delete_message(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_button_when_message_missing_and_fetch_channel_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(None)
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(None)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(message)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_button_when_message_missing_and_get_message_fails(
        self,
        decoy_channel: discord.TextChannel,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        decoy: Decoy,
    ) -> None:
        with mock_operations(decoy, leave_action):
            decoy.when(
                await operations.safe_original_response(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(None)
            decoy.when(
                await operations.safe_fetch_text_channel(
                    client=ANY,
                    guild_xid=ANY,
                    channel_xid=ANY,
                ),
                ignore_extra_args=True,
            ).then_return(decoy_channel)
            decoy.when(
                operations.safe_get_partial_message(channel=ANY, guild_xid=ANY, message_xid=ANY),
                ignore_extra_args=True,
            ).then_return(None)
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_update_embed(message=ANY),
                times=0,
                ignore_extra_args=True,
            )

    async def test_leave_button_when_defer_fails(
        self,
        cog: LeaveGameCog,
        message: discord.Message,
        player: User,
        interaction: discord.Interaction,
        game: Game,
        bot: SpellBot,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        safe_defer_interaction_fake = stub(lfg_view, "safe_defer_interaction")
        decoy.when(
            await safe_defer_interaction_fake(interaction=ANY),
            ignore_extra_args=True,
        ).then_return(False)
        with mock_operations(decoy, leave_action):
            view = GameView(bot)

            await view.leave(interaction)

            decoy.verify(
                await operations.safe_update_embed_origin(interaction=ANY),
                times=0,
                ignore_extra_args=True,
            )
            decoy.verify(
                await operations.safe_delete_message(message=ANY),
                times=0,
                ignore_extra_args=True,
            )
