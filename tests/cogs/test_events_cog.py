from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy.sql.expression import and_

from spellbot.actions import lfg_action
from spellbot.cogs import EventsCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat
from spellbot.models import Game, GameStatus, Play, User
from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    import discord

    from spellbot.client import SpellBot


@pytest.fixture
def cog(bot: SpellBot) -> EventsCog:
    return EventsCog(bot)


@pytest.mark.asyncio
class TestCogEvents(InteractionMixin):
    async def test_game(
        self,
        cog: EventsCog,
        message: discord.Message,
        add_user: Callable[..., User],
    ) -> None:
        player1 = add_user()
        player2 = add_user()
        users = [mock_discord_object(player1), mock_discord_object(player2)]
        with mock_operations(lfg_action, users=users):
            lfg_action.safe_followup_channel.return_value = message

            await self.run(
                cog.game,
                players=f"<@{player1.xid}><@{player2.xid}>",
                format=cast(int, GameFormat.LEGACY.value),
            )

        game = DatabaseSession.query(Game).one()
        assert game.status == GameStatus.STARTED.value
        admin = DatabaseSession.query(User).get(self.interaction.user.id)
        assert admin is not None
        assert self.interaction.channel is not None
        assert admin.game(self.interaction.channel.id) is None
        players = DatabaseSession.query(User).filter(User.xid != self.interaction.user.id).all()
        assert len(players) == 2
        for player in players:
            play = (
                DatabaseSession.query(Play)
                .filter(
                    and_(
                        Play.user_xid == player.xid,
                        Play.game_id == game.id,
                    ),
                )
                .one_or_none()
            )
            assert play is not None

    async def test_game_with_one_player(
        self,
        cog: EventsCog,
        add_user: Callable[..., User],
    ) -> None:
        player = add_user()
        users = [mock_discord_object(player)]
        with mock_operations(lfg_action, users=users):
            await self.run(
                cog.game,
                players=f"<@{player.xid}>",
                format=cast(int, GameFormat.LEGACY.value),
            )

            lfg_action.safe_followup_channel.assert_called_once_with(
                self.interaction,
                "You can't create a Legacy game with 1 players.",
            )

    async def test_game_with_banned_player(
        self,
        cog: EventsCog,
        add_user: Callable[..., User],
    ) -> None:
        player = add_user()
        banned = add_user(banned=True)
        users = [mock_discord_object(player), mock_discord_object(banned)]
        with mock_operations(lfg_action, users=users):
            await self.run(
                cog.game,
                players=f"<@{player.xid}><@{banned.xid}>",
                format=cast(int, GameFormat.LEGACY.value),
            )

            lfg_action.safe_followup_channel.assert_called_once_with(
                self.interaction,
                f"Some of the players you mentioned can not be added to a game: <@{banned.xid}>",
            )
