from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import discord
import pytest
import pytest_asyncio
from sqlalchemy.sql.expression import and_

from spellbot.actions import lfg_action
from spellbot.cogs import EventsCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat, GameService
from spellbot.models import Game, GameStatus, Guild, Play, User
from tests.mixins import InteractionMixin
from tests.mocks import mock_discord_object, mock_operations

if TYPE_CHECKING:
    from collections.abc import Callable

    from spellbot.client import SpellBot

pytestmark = pytest.mark.use_db


@pytest.fixture
def cog(bot: SpellBot) -> EventsCog:
    return EventsCog(bot)


@pytest_asyncio.fixture
async def make_voice_channel() -> Callable[..., discord.VoiceChannel]:
    def factory(
        discord_guild: discord.Guild,
        id: int,
        name: str,
        perms: discord.Permissions,
        created_at: datetime,
    ) -> discord.VoiceChannel:
        voice = MagicMock(spec=discord.VoiceChannel)
        voice.id = id
        voice.name = name
        voice.guild = discord_guild
        voice.type = discord.ChannelType.voice
        voice.permissions_for = MagicMock(return_value=perms)
        voice.created_at = created_at
        return voice

    return factory


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
                format=cast("int", GameFormat.LEGACY.value),
            )

        game = DatabaseSession.query(Game).one()
        assert game.status == GameStatus.STARTED.value
        admin = DatabaseSession.get(User, self.interaction.user.id)
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
                format=cast("int", GameFormat.LEGACY.value),
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
                format=cast("int", GameFormat.LEGACY.value),
            )

            lfg_action.safe_followup_channel.assert_called_once_with(
                self.interaction,
                f"Some of the players you mentioned can not be added to a game: <@{banned.xid}>",
            )

    async def test_game_with_voice_channel(
        self,
        cog: EventsCog,
        guild: Guild,
        message: discord.Message,
        make_voice_channel: Callable[..., discord.VoiceChannel],
    ) -> None:
        discord_guild = mock_discord_object(guild)
        user_1 = self.factories.user.create()
        user_2 = self.factories.user.create()
        discord_user_1 = mock_discord_object(user_1)
        discord_user_2 = mock_discord_object(user_2)
        guild.voice_create = True  # type: ignore
        DatabaseSession.commit()
        channel = self.factories.channel.create(guild=guild, voice_invite=True)
        message.channel.id = channel.xid
        manage_perms = discord.Permissions(discord.Permissions.manage_channels.flag)
        voice_channel = make_voice_channel(
            discord_guild,
            id=4001,
            name="does-not-matter",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC),
        )
        voice_invite = MagicMock(spec=discord.Invite, url="http://example")

        with mock_operations(lfg_action, users=[discord_user_1, discord_user_2]):
            lfg_action.safe_followup_channel.return_value = message
            lfg_action.safe_create_voice_channel.return_value = voice_channel
            lfg_action.safe_create_channel_invite.return_value = voice_invite

            await self.run(
                cog.game,
                players=f"<@{user_1.xid}><@{user_2.xid}>",
                format=GameFormat.MODERN.value,
                service=GameService.NOT_ANY.value,
            )

        game = DatabaseSession.query(Game).one()
        assert game.voice_xid == voice_channel.id
        assert game.voice_invite_link == voice_invite.url
