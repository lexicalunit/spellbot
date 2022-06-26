from __future__ import annotations

import discord
import pytest
from discord_slash.context import InteractionContext

from spellbot import SpellBot
from spellbot.cogs import EventsCog
from spellbot.database import DatabaseSession
from spellbot.interactions import lfg_interaction
from spellbot.models import Game, GameFormat, GameStatus, User
from tests.factories.user import UserFactory
from tests.mocks import (
    build_author,
    build_client_user,
    build_message,
    mock_discord_user,
    mock_operations,
)


@pytest.mark.asyncio
class TestCogEvents:
    async def test_game(self, bot: SpellBot, ctx: InteractionContext):
        assert ctx.guild
        assert ctx.channel
        assert isinstance(ctx.channel, discord.TextChannel)
        assert isinstance(ctx.author, discord.User)
        player1 = build_author(1)
        player2 = build_author(2)
        client_user = build_client_user()
        game_post = build_message(ctx.guild, ctx.channel, client_user)

        with mock_operations(lfg_interaction, users=[ctx.author, player1, player2]):
            lfg_interaction.safe_send_channel.return_value = game_post
            cog = EventsCog(bot)
            await cog.game.func(
                cog,
                ctx,
                f"<@{player1.id}><@{player2.id}>",
                GameFormat.LEGACY.value,
            )

        game = DatabaseSession.query(Game).one()
        assert game.status == GameStatus.STARTED.value
        users = DatabaseSession.query(User).all()
        assert len(users) == 2
        for user in users:
            assert user.game_id == game.id

    async def test_game_with_one_player(self, bot: SpellBot, ctx: InteractionContext):
        assert isinstance(ctx.author, discord.User)
        player = build_author(1)

        with mock_operations(lfg_interaction, users=[ctx.author, player]):
            cog = EventsCog(bot)
            await cog.game.func(cog, ctx, f"<@{player.id}>", GameFormat.LEGACY.value)
            lfg_interaction.safe_send_channel.assert_called_once_with(
                ctx,
                "You can't create a Legacy game with 1 players.",
            )

    async def test_game_with_banned_player(self, bot: SpellBot, ctx: InteractionContext):
        assert isinstance(ctx.author, discord.User)
        player = build_author(1)
        banned_user = UserFactory.create(banned=True)
        banned_player = mock_discord_user(banned_user)

        with mock_operations(lfg_interaction, users=[ctx.author, player, banned_player]):
            cog = EventsCog(bot)
            await cog.game.func(
                cog,
                ctx,
                f"<@{player.id}><@{banned_player.id}>",
                GameFormat.LEGACY.value,
            )
            lfg_interaction.safe_send_channel.assert_called_once_with(
                ctx,
                (
                    "Some of the players you mentioned can not"
                    f" be added to a game: <@{banned_user.xid}>"
                ),
            )
