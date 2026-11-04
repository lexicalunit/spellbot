# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import discord
import pytest
import pytest_asyncio
from decoy import matchers
from sqlalchemy import select, update
from sqlalchemy.sql.expression import and_

from spellbot import operations
from spellbot.actions import lfg_action
from spellbot.cogs import EventsCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat, GameService
from spellbot.models import Channel, Game, GameStatus, Guild, Play, User
from spellbot.services.users import current_game
from tests.fixtures import run_command
from tests.mocks import mock_discord_object, mock_operations
from tests.mocks.decoys import ANY

if TYPE_CHECKING:
    from collections.abc import Callable

    from decoy import Decoy

    from spellbot import SpellBot
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest.fixture
def cog(bot: SpellBot) -> EventsCog:
    return EventsCog(bot)


@pytest_asyncio.fixture
async def make_voice_channel(decoy: Decoy) -> Callable[..., discord.VoiceChannel]:
    def factory(
        discord_guild: discord.Guild,
        id: int,
        name: str,
        perms: discord.Permissions,
        created_at: datetime,
    ) -> discord.VoiceChannel:
        voice = decoy.mock(cls=discord.VoiceChannel)
        voice.id = id
        voice.name = name
        voice.guild = discord_guild
        decoy.when(voice.type).then_return(discord.ChannelType.voice)
        decoy.when(voice.permissions_for(matchers.Anything())).then_return(perms)
        decoy.when(voice.created_at).then_return(created_at)
        return voice

    return factory


@pytest.mark.asyncio
class TestCogEvents:
    async def test_game_options_are_described(self, cog: EventsCog) -> None:
        descriptions = {param.name: param.description for param in cog.game.parameters}
        assert descriptions["format"] == "What game format do you want to play?"
        assert descriptions["bracket"] == "What commander bracket do you want to play?"

    async def test_game(
        self,
        cog: EventsCog,
        message: discord.Message,
        add_user: Callable[..., User],
        interaction: discord.Interaction,
        guild: Guild,
        decoy: Decoy,
    ) -> None:
        player1 = add_user()
        player2 = add_user()
        users = [mock_discord_object(decoy, player1), mock_discord_object(decoy, player2)]
        with mock_operations(decoy, lfg_action, users=users):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)

            await run_command(
                cog.game,
                interaction,
                players=f"<@{player1.xid}><@{player2.xid}>",
                format=cast("int", GameFormat.LEGACY.value),
            )

        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert game.status == GameStatus.STARTED.value
        admin = await DatabaseSession.get(User, interaction.user.id)
        assert admin is not None
        assert interaction.channel is not None
        assert await current_game(admin.xid, interaction.channel.id) is None
        # Verify the specific players we created are in the game
        for player_xid in [player1.xid, player2.xid]:
            play = (
                await DatabaseSession.execute(
                    select(Play).where(
                        and_(
                            Play.user_xid == player_xid,
                            Play.game_id == game.id,
                        ),
                    ),
                )
            ).scalar_one_or_none()
            assert play is not None

    async def test_game_snapshots_channel_modes(
        self,
        cog: EventsCog,
        message: discord.Message,
        add_user: Callable[..., User],
        interaction: discord.Interaction,
        channel: Channel,
        decoy: Decoy,
    ) -> None:
        await DatabaseSession.execute(
            update(Channel)
            .where(Channel.xid == channel.xid)
            .values(to_mode=True, competitive_mode=True),
        )
        await DatabaseSession.commit()
        player1 = add_user()
        player2 = add_user()
        users = [mock_discord_object(decoy, player1), mock_discord_object(decoy, player2)]
        with mock_operations(decoy, lfg_action, users=users):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)
            await run_command(
                cog.game,
                interaction,
                players=f"<@{player1.xid}><@{player2.xid}>",
                format=cast("int", GameFormat.LEGACY.value),
            )

        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert game.to_mode is True
        assert game.competitive_mode is True

    async def test_game_with_one_player(
        self,
        cog: EventsCog,
        add_user: Callable[..., User],
        interaction: discord.Interaction,
        guild: Guild,
        decoy: Decoy,
    ) -> None:
        player = add_user()
        users = [mock_discord_object(decoy, player)]
        with mock_operations(decoy, lfg_action, users=users):
            await run_command(
                cog.game,
                interaction,
                players=f"<@{player.xid}>",
                format=cast("int", GameFormat.LEGACY.value),
            )

            decoy.verify(
                await operations.safe_followup_channel(
                    interaction,
                    "You can't create a Legacy game with 1 players.",
                ),
                times=1,
            )

    async def test_game_with_banned_player(
        self,
        cog: EventsCog,
        add_user: Callable[..., User],
        interaction: discord.Interaction,
        guild: Guild,
        decoy: Decoy,
    ) -> None:
        player = add_user()
        banned = add_user(banned=True)
        users = [mock_discord_object(decoy, player), mock_discord_object(decoy, banned)]
        with mock_operations(decoy, lfg_action, users=users):
            await run_command(
                cog.game,
                interaction,
                players=f"<@{player.xid}><@{banned.xid}>",
                format=cast("int", GameFormat.LEGACY.value),
            )

            decoy.verify(
                await operations.safe_followup_channel(
                    interaction,
                    "Some of the players you mentioned can not be added to a game: "
                    f"<@{banned.xid}>",
                ),
                times=1,
            )

    async def test_game_with_voice_channel(
        self,
        cog: EventsCog,
        guild: Guild,
        message: discord.Message,
        make_voice_channel: Callable[..., discord.VoiceChannel],
        interaction: discord.Interaction,
        factories: Factories,
        decoy: Decoy,
    ) -> None:
        discord_guild = mock_discord_object(decoy, guild)
        user_1 = factories.user.create()
        user_2 = factories.user.create()
        discord_user_1 = mock_discord_object(decoy, user_1)
        discord_user_2 = mock_discord_object(decoy, user_2)
        guild.voice_create = True
        await DatabaseSession.commit()
        channel = factories.channel.create(guild=guild, voice_invite=True)
        message.channel.id = channel.xid
        manage_perms = discord.Permissions(discord.Permissions.manage_channels.flag)
        voice_channel = make_voice_channel(
            discord_guild,
            id=4001,
            name="does-not-matter",
            perms=manage_perms,
            created_at=datetime.now(tz=UTC),
        )
        voice_invite = decoy.mock(cls=discord.Invite)
        decoy.when(voice_invite.url).then_return("http://example")

        with mock_operations(decoy, lfg_action, users=[discord_user_1, discord_user_2]):
            decoy.when(
                await operations.safe_followup_channel(interaction=ANY),
                ignore_extra_args=True,
            ).then_return(message)
            decoy.when(
                await operations.safe_ensure_voice_category(ANY, guild.xid, ANY),
            ).then_return(decoy.mock(cls=discord.CategoryChannel))
            decoy.when(
                await operations.safe_create_voice_channel(client=ANY, guild_xid=ANY, name=ANY),
                ignore_extra_args=True,
            ).then_return(voice_channel)
            decoy.when(
                await operations.safe_create_channel_invite(channel=ANY),
                ignore_extra_args=True,
            ).then_return(voice_invite)

            await run_command(
                cog.game,
                interaction,
                players=f"<@{user_1.xid}><@{user_2.xid}>",
                format=GameFormat.MODERN.value,
                service=GameService.NOT_ANY.value,
            )

        game = (await DatabaseSession.execute(select(Game))).scalar_one()
        assert game.voice_xid == voice_channel.id
        assert game.voice_invite_link == voice_invite.url
