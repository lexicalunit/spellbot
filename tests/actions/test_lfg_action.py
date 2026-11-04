# Copyright (c) 2026 spellbot@lexicalunit.com

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import discord
import pytest
import pytest_asyncio
from decoy import matchers

from spellbot import services
from spellbot.actions import (
    LookingForGameAction,
    base_action,
    game_posts,
    game_start,
    guild_war,
    lfg_action,
)
from spellbot.data import GameCriteria, GameLinkDetails, PostData
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.integrations import convoke
from spellbot.models import MAX_RULES_LENGTH
from spellbot.operations import VoiceChannelSuggestion
from spellbot.services.awards import NewAward
from spellbot.settings import settings
from tests.mocks import create_mock_game, create_mock_guild, create_mock_user, mock_discord_object
from tests.mocks.decoys import ANY, captured

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from decoy import Decoy

    from spellbot import SpellBot
    from spellbot.integrations.convoke import LiveGuildWar
    from spellbot.models import User
    from tests.fixtures import Stub

from datetime import UTC, datetime

pytestmark = pytest.mark.use_db


def create_test_post(
    game_id: int = 1,
    guild_xid: int = 99999,
    channel_xid: int = 88888,
    message_xid: int = 77777,
) -> PostData:
    """Create a PostData object for tests."""
    now = datetime.now(tz=UTC)
    return PostData(
        created_at=now,
        updated_at=now,
        game_id=game_id,
        guild_xid=guild_xid,
        channel_xid=channel_xid,
        message_xid=message_xid,
    )


@pytest_asyncio.fixture
async def action(bot: SpellBot, interaction: discord.Interaction) -> LookingForGameAction:
    async with LookingForGameAction.create(bot, interaction) as action:
        return action


@pytest.mark.asyncio
class TestLookingForGameAction:
    async def test_resolve_criteria_keeps_requested_options(
        self,
        action: LookingForGameAction,
    ) -> None:
        criteria = action.resolve_criteria(
            seats=2,
            rules="be nice",
            format=GameFormat.PAUPER.value,
            bracket=GameBracket.BRACKET_1.value,
            service=GameService.X_MAGE.value,
        )
        assert criteria == GameCriteria(
            seats=2,
            format=GameFormat.PAUPER.value,
            bracket=GameBracket.BRACKET_1.value,
            service=GameService.X_MAGE.value,
            rules="be nice",
        )

    async def test_resolve_criteria_falls_back_to_channel_defaults(
        self,
        action: LookingForGameAction,
    ) -> None:
        action.channel_data.default_format = GameFormat.PAUPER
        action.channel_data.default_bracket = GameBracket.BRACKET_1
        action.channel_data.default_service = GameService.X_MAGE
        criteria = action.resolve_criteria()
        assert criteria.format == GameFormat.PAUPER.value
        assert criteria.bracket == GameBracket.BRACKET_1.value
        assert criteria.service == GameService.X_MAGE.value
        # Without explicit seats the game seats as many players as its format needs.
        assert criteria.seats == GameFormat.PAUPER.players

    async def test_resolve_criteria_caps_seats_at_the_service_maximum(
        self,
        action: LookingForGameAction,
    ) -> None:
        criteria = action.resolve_criteria(seats=99, service=GameService.PLAYGROUP_LIVE.value)
        assert criteria.seats == GameService.PLAYGROUP_LIVE.max_seats

    async def test_resolve_criteria_truncates_rules(self, action: LookingForGameAction) -> None:
        criteria = action.resolve_criteria(rules="x" * (MAX_RULES_LENGTH + 10))
        assert criteria.rules == "x" * MAX_RULES_LENGTH

    @pytest.mark.parametrize(
        ("format", "bracket", "actual"),
        [
            pytest.param(None, None, GameBracket.NONE.value, id="none"),
            pytest.param(GameFormat.CEDH.value, None, GameBracket.BRACKET_5.value, id="cedh"),
            pytest.param(
                GameFormat.CEDH.value,
                GameBracket.BRACKET_1.value,
                GameBracket.BRACKET_5.value,
                id="cedh-override",
            ),
            pytest.param(
                GameFormat.PRE_CONS.value,
                None,
                GameBracket.BRACKET_2.value,
                id="precons",
            ),
            pytest.param(
                GameFormat.COMMANDER.value,
                GameBracket.BRACKET_1.value,
                GameBracket.BRACKET_1.value,
                id="commander",
            ),
        ],
    )
    async def test_resolve_criteria_bracket(
        self,
        action: LookingForGameAction,
        format: int | None,
        bracket: int | None,
        actual: int,
    ) -> None:
        assert action.resolve_criteria(format=format, bracket=bracket).bracket == actual

    async def test_resolve_criteria_bracket_channel_default(
        self,
        action: LookingForGameAction,
    ) -> None:
        action.channel_data.default_bracket = GameBracket.BRACKET_1
        assert action.resolve_criteria().bracket == GameBracket.BRACKET_1.value

    async def test_execute_in_non_guild_channel(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action, "guild", None)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        fake = stub(lfg_action, "safe_send_user")

        result = await action.execute()

        assert result is None
        decoy.verify(
            await fake(discord_user, "Sorry, that command is not supported in this context."),
            times=1,
        )

    async def test_execute_rematch_no_guild(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        """Test execute_rematch when guild is None."""
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action, "guild", None)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        fake = stub(lfg_action, "safe_send_user")

        await action.execute_rematch()

        decoy.verify(
            await fake(
                discord_user,
                "Please run this command in the same channel as your last played game.",
            ),
            times=1,
        )

    async def test_execute_rematch_no_channel(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        """Test execute_rematch when channel is None."""
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action, "channel", None)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        fake = stub(lfg_action, "safe_send_user")

        await action.execute_rematch()

        decoy.verify(
            await fake(
                discord_user,
                "Please run this command in the same channel as your last played game.",
            ),
            times=1,
        )

    async def test_execute_rematch_pending_games(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test execute_rematch when user already has pending games."""
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(1)
        fake = stub(lfg_action, "safe_followup_channel")

        await action.execute_rematch()

        decoy.verify(
            await fake(
                action.interaction,
                "You're already in a pending game, leave that one first.",
            ),
            times=1,
        )

    async def test_execute_rematch_no_last_game(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test execute_rematch when user has no last game."""
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(0)
        get_last_game_fake = stub(services.games, "get_last_game")
        decoy.when(await get_last_game_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        fake = stub(lfg_action, "safe_followup_channel")

        await action.execute_rematch()

        decoy.verify(
            await fake(action.interaction, "You have not played a game in this guild yet."),
            times=1,
        )

    async def test_execute_already_waiting_origin(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        """Test execute when user is already waiting from button (origin=True)."""
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(
            create_mock_game(game_id=1)
        )
        fake = stub(lfg_action, "safe_send_user")

        # message_xid makes origin=True
        await action.execute(message_xid=12345)

        decoy.verify(await fake(discord_user, "You're already in a game in this channel."), times=1)

    async def test_execute_too_many_pending_games_origin(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        """Test execute when user has too many pending games (from button)."""
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(
            settings.MAX_PENDING_GAMES
        )
        fake = stub(lfg_action, "safe_send_user")

        # message_xid makes origin=True
        await action.execute(message_xid=12345)

        decoy.verify(
            await fake(
                discord_user,
                "You're in too many pending games to join another one at this time.",
            ),
            times=1,
        )

    async def test_execute_too_many_pending_games_non_origin(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test execute when user has too many pending games (from slash command)."""
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(
            settings.MAX_PENDING_GAMES
        )
        fake = stub(lfg_action, "safe_followup_channel")

        # No message_xid means origin=False (slash command)
        result = await action.execute()

        assert result is None
        decoy.verify(
            await fake(
                action.interaction,
                "You're in too many pending games to join another one at this time.",
            ),
            times=1,
        )

    async def test_update_other_game_posts_no_games(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _update_other_game_posts returns early when no other game IDs."""
        # Should return immediately without calling message_xids
        fake = stub(services.games, "message_xids")
        await action.game_posts.update_other_game_posts([])
        decoy.verify(await fake(ANY), times=0, ignore_extra_args=True)

    async def test_join_game_filled_up(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Joining a game that fills up before add_player runs warns the user."""
        # message_xid makes origin=True, routing through the join (not create) path.
        get_by_message_xid_fake = stub(services.games, "get_by_message_xid")
        decoy.when(await get_by_message_xid_fake(ANY), ignore_extra_args=True).then_return(
            create_mock_game(game_id=1)
        )
        blocked_fake = stub(services.games, "blocked")
        decoy.when(await blocked_fake(ANY, ANY), ignore_extra_args=True).then_return(False)
        # The game filled up between fetch and add_player, so it returns None.
        add_player_fake = stub(services.games, "add_player")
        decoy.when(await add_player_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        fake = stub(lfg_action, "safe_send_user")

        game = await action.join_game(12345)

        assert game is None
        decoy.verify(await fake(ANY), times=1, ignore_extra_args=True)

    async def test_update_other_game_posts_with_games(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Every post of another game is refreshed in its own channel, by its own message id."""
        now = datetime.now(tz=UTC)
        posts = [
            PostData(
                created_at=now,
                updated_at=now,
                game_id=1,
                guild_xid=67890,
                channel_xid=channel_xid,
                message_xid=message_xid,
            )
            for channel_xid, message_xid in ((12345, 111), (54321, 222))
        ]
        game_data = replace(
            create_mock_game(game_id=1, channel_xid=12345, guild_xid=67890),
            players=[create_mock_user()],
            posts=posts,
        )
        get_many_fake = stub(services.games, "get_many")
        decoy.when(await get_many_fake(ANY), ignore_extra_args=True).then_return([game_data])
        fetch_stub = stub(base_action, "safe_fetch_text_channel")
        decoy.when(await fetch_stub(ANY, ANY, ANY), ignore_extra_args=True).then_return(
            decoy.mock(cls=discord.TextChannel)
        )
        get_stub = stub(base_action, "safe_get_partial_message")
        decoy.when(get_stub(ANY, ANY, ANY), ignore_extra_args=True).then_return(
            decoy.mock(cls=discord.PartialMessage)
        )
        update_stub = stub(base_action, "safe_update_embed")
        decoy.when(await update_stub(ANY), ignore_extra_args=True).then_return(True)

        await action.game_posts.update_other_game_posts([1])

        for channel_xid, message_xid in ((12345, 111), (54321, 222)):
            decoy.verify(await fetch_stub(matchers.Anything(), 67890, channel_xid), times=1)
            decoy.verify(get_stub(matchers.Anything(), 67890, message_xid), times=1)
        decoy.verify(await update_stub(ANY, embed=matchers.IsA(discord.Embed), view=ANY), times=2)

    async def test_update_other_game_posts_no_data(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _update_other_game_posts skips when no game data found."""
        get_many_fake = stub(services.games, "get_many")
        decoy.when(await get_many_fake(ANY), ignore_extra_args=True).then_return([])
        update_stub = stub(base_action, "safe_update_embed")

        await action.game_posts.update_other_game_posts([1])

        decoy.verify(await update_stub(ANY), times=0, ignore_extra_args=True)

    async def test_update_other_game_posts_channel_not_found(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _update_other_game_posts skips when channel not found."""
        game_data = create_mock_game(game_id=1, channel_xid=123, guild_xid=456)
        message_xids_fake = stub(services.games, "message_xids")
        decoy.when(await message_xids_fake(ANY), ignore_extra_args=True).then_return([111])
        get_by_message_xid_fake = stub(services.games, "get_by_message_xid")
        decoy.when(await get_by_message_xid_fake(ANY), ignore_extra_args=True).then_return(
            game_data
        )
        safe_fetch_text_channel_fake = stub(game_posts, "safe_fetch_text_channel")
        decoy.when(
            await safe_fetch_text_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(None)

        update_stub = stub(game_posts, "safe_update_embed")

        await action.game_posts.update_other_game_posts([1])

        decoy.verify(await update_stub(ANY), times=0, ignore_extra_args=True)

    async def test_ensure_users_exist_user_not_found(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test ensure_users_exist when user cannot be fetched."""
        safe_fetch_user_fake = stub(lfg_action, "safe_fetch_user")
        decoy.when(await safe_fetch_user_fake(ANY, ANY), ignore_extra_args=True).then_return(None)

        result = await action.ensure_users_exist([99999])

        assert result == []

    async def test_ensure_users_exist_excludes_self(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test ensure_users_exist excludes self when exclude_self=True."""
        self_id = action.interaction.user.id
        fetch_stub = stub(lfg_action, "safe_fetch_user")

        result = await action.ensure_users_exist([self_id], exclude_self=True)

        assert result == []
        decoy.verify(await fetch_stub(ANY, ANY), times=0, ignore_extra_args=True)

    async def test_handle_voice_creation_no_category(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test handle_voice_creation returns when category not found."""
        game_data = create_mock_game(game_id=1)
        action.guild_data = create_mock_guild(
            voice_create=True,
            use_max_bitrate=False,
        )
        safe_ensure_voice_category_fake = stub(game_start, "safe_ensure_voice_category")
        decoy.when(
            await safe_ensure_voice_category_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(None)
        voice_stub = stub(game_start, "safe_create_voice_channel")

        await action.game_start.handle_voice_creation(game_data, 12345)

        decoy.verify(await voice_stub(ANY, ANY, ANY), times=0, ignore_extra_args=True)

    async def test_handle_voice_creation_no_category_prefix(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test handle_voice_creation returns early when channel has no voice_category."""
        game_data = create_mock_game(game_id=1)
        action.guild_data = create_mock_guild(
            voice_create=True,
            use_max_bitrate=False,
        )
        action.channel_data.voice_category = None
        ensure_stub = stub(game_start, "safe_ensure_voice_category")

        result = await action.game_start.handle_voice_creation(game_data, 12345)

        assert result is game_data
        decoy.verify(await ensure_stub(ANY, ANY, ANY), times=0, ignore_extra_args=True)

    async def test_handle_voice_creation_no_voice_channel(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test handle_voice_creation returns when voice channel creation fails."""
        game_data = create_mock_game(game_id=1)
        mock_category = decoy.mock(cls=discord.CategoryChannel)
        action.guild_data = create_mock_guild(
            voice_create=True,
            use_max_bitrate=False,
        )
        safe_ensure_voice_category_fake = stub(game_start, "safe_ensure_voice_category")
        decoy.when(
            await safe_ensure_voice_category_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_category)
        safe_create_voice_channel_fake = stub(game_start, "safe_create_voice_channel")
        decoy.when(
            await safe_create_voice_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(None)

        set_voice_stub = stub(services.games, "set_voice")

        await action.game_start.handle_voice_creation(game_data, 12345)

        decoy.verify(await set_voice_stub(ANY, voice_xid=ANY), times=0, ignore_extra_args=True)

    async def test_handle_voice_creation_with_invite(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test handle_voice_creation creates voice invite when configured."""
        game_data = create_mock_game(game_id=1)
        mock_category = decoy.mock(cls=discord.CategoryChannel)
        mock_voice_channel = decoy.mock(cls=discord.VoiceChannel)
        mock_voice_channel.id = 99999
        mock_invite = decoy.mock(cls=discord.Invite)
        decoy.when(mock_invite.url).then_return("https://discord.gg/invite")

        action.guild_data = create_mock_guild(
            voice_create=True,
            use_max_bitrate=False,
        )
        safe_ensure_voice_category_fake = stub(game_start, "safe_ensure_voice_category")
        decoy.when(
            await safe_ensure_voice_category_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_category)
        safe_create_voice_channel_fake = stub(game_start, "safe_create_voice_channel")
        decoy.when(
            await safe_create_voice_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_voice_channel)
        safe_create_channel_invite_fake = stub(game_start, "safe_create_channel_invite")
        decoy.when(await safe_create_channel_invite_fake(ANY), ignore_extra_args=True).then_return(
            mock_invite
        )

        # Enable voice invite
        action.channel_data.voice_invite = True

        set_voice_stub = stub(services.games, "set_voice")
        decoy.when(await set_voice_stub(ANY, voice_xid=ANY), ignore_extra_args=True).then_return(
            game_data
        )

        await action.game_start.handle_voice_creation(game_data, 12345)

        decoy.verify(
            await set_voice_stub(
                game_data,
                voice_xid=99999,
                voice_invite_link="https://discord.gg/invite",
            ),
            times=1,
        )

    async def test_handle_voice_creation_without_invite(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test handle_voice_creation without voice invite."""
        game_data = create_mock_game(game_id=1)
        mock_category = decoy.mock(cls=discord.CategoryChannel)
        mock_voice_channel = decoy.mock(cls=discord.VoiceChannel)
        mock_voice_channel.id = 99999

        action.guild_data = create_mock_guild(
            voice_create=True,
            use_max_bitrate=False,
        )
        safe_ensure_voice_category_fake = stub(game_start, "safe_ensure_voice_category")
        decoy.when(
            await safe_ensure_voice_category_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_category)
        safe_create_voice_channel_fake = stub(game_start, "safe_create_voice_channel")
        decoy.when(
            await safe_create_voice_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_voice_channel)
        invite_stub = stub(game_start, "safe_create_channel_invite")

        # voice_invite is False by default
        action.channel_data.voice_invite = False

        set_voice_stub = stub(services.games, "set_voice")
        decoy.when(await set_voice_stub(ANY, voice_xid=ANY), ignore_extra_args=True).then_return(
            game_data
        )

        await action.game_start.handle_voice_creation(game_data, 12345)

        decoy.verify(await invite_stub(ANY), times=0, ignore_extra_args=True)
        decoy.verify(
            await set_voice_stub(game_data, voice_xid=99999, voice_invite_link=None),
            times=1,
        )

    async def test_make_game_ready_with_voice_suggestion(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test make_game_ready calls safe_suggest_voice_channel when conditions are met."""
        game_data = create_mock_game(game_id=1)
        action.guild_data = create_mock_guild(
            xid=12345,
            name="Test Guild",
            suggest_voice_category="Voice Channels",
        )

        mock_suggestion = VoiceChannelSuggestion(already_picked=None, random_empty=None)
        safe_suggest_voice_channel_fake = stub(game_start, "safe_suggest_voice_channel")
        decoy.when(
            safe_suggest_voice_channel_fake(guild=ANY, category=ANY, player_xids=ANY),
            ignore_extra_args=True,
        ).then_return(mock_suggestion)
        create_game_link_fake = stub(action.bot, "create_game_link")
        decoy.when(await create_game_link_fake(ANY), ignore_extra_args=True).then_return(
            GameLinkDetails("https://game.link", None)
        )
        make_ready_fake = stub(services.games, "make_ready")
        decoy.when(await make_ready_fake(ANY, ANY, ANY), ignore_extra_args=True).then_return(
            game_data
        )

        _, suggested_vc = await action.game_start.make_game_ready(game_data, [123, 456])

        assert suggested_vc == mock_suggestion

    async def test_make_game_ready_reuses_existing_convoke_link(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(
            game_id=1,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            game_link="https://convoke.games/en/play/already",
            password="kept",  # noqa: S106
            convoke_guild_name="Cool Guild",
            convoke_guild_url="https://convoke.games/en/guild/cool",
        )
        create_link = stub(action.bot, "create_game_link")
        update_players = stub(action.bot, "update_game_players")
        make_ready = stub(services.games, "make_ready")
        decoy.when(await make_ready(ANY, ANY, ANY), ignore_extra_args=True).then_return(game_data)

        await action.game_start.make_game_ready(game_data, [123, 456])

        decoy.verify(await create_link(ANY), times=0, ignore_extra_args=True)
        # The guild found when the table was opened is kept, not wiped by the early link.
        details = GameLinkDetails(
            "https://convoke.games/en/play/already",
            "kept",
            "Cool Guild",
            "https://convoke.games/en/guild/cool",
        )
        pins = matchers.ValueCaptor[dict[int, str]]()
        decoy.verify(await make_ready(game_data, details, pins.matcher), times=1)
        # The pins sent to Convoke with the final roster are the pins the players are given.
        pins_value = captured(pins, dict)
        assert set(pins_value) == {123, 456}
        decoy.verify(await update_players(game_data, pins_value), times=1)

    async def test_make_game_ready_sends_player_pins_with_new_link(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(game_id=1)
        create_link = stub(action.bot, "create_game_link")
        decoy.when(await create_link(ANY), ignore_extra_args=True).then_return(
            GameLinkDetails("https://convoke.games/en/play/new", None)
        )
        update_players = stub(action.bot, "update_game_players")
        make_ready = stub(services.games, "make_ready")
        decoy.when(await make_ready(ANY, ANY, ANY), ignore_extra_args=True).then_return(game_data)

        await action.game_start.make_game_ready(game_data, [123, 456])

        decoy.verify(await update_players(ANY, ANY), times=0, ignore_extra_args=True)
        pins = matchers.ValueCaptor[dict[int, str]]()
        decoy.verify(await make_ready(game_data, matchers.Anything(), pins.matcher), times=1)
        pins_value = captured(pins, dict)
        assert set(pins_value) == {123, 456}
        decoy.verify(await create_link(game_data, pins_value, original_seats=None), times=1)

    async def test_ensure_guild_war_convoke_link_attaches_new_table(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(
            game_id=7,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        game_data.players = [create_mock_user(xid=100)]
        attached = create_mock_game(
            game_id=7,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            game_link="https://convoke.games/en/play/new",
        )
        create_link = stub(action.bot, "create_game_link")
        decoy.when(await create_link(ANY), ignore_extra_args=True).then_return(
            GameLinkDetails("https://convoke.games/en/play/new", None)
        )
        attach = stub(services.games, "attach_game_link")
        decoy.when(await attach(ANY, ANY), ignore_extra_args=True).then_return(attached)

        result = await action.guild_war.ensure_guild_war_convoke_link(game_data)

        decoy.verify(await create_link(game_data), times=1)
        decoy.verify(
            await attach(game_data, GameLinkDetails("https://convoke.games/en/play/new", None)),
            times=1,
        )
        assert result.game_link == "https://convoke.games/en/play/new"

    async def test_ensure_guild_war_convoke_link_skips_when_already_open(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(
            game_id=7,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            game_link="https://convoke.games/en/play/existing",
        )
        create_link = stub(action.bot, "create_game_link")

        result = await action.guild_war.ensure_guild_war_convoke_link(game_data)

        decoy.verify(await create_link(ANY), times=0, ignore_extra_args=True)
        assert result.game_link == "https://convoke.games/en/play/existing"

    async def test_ensure_guild_war_convoke_link_skips_when_not_a_war(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(game_id=7)
        create_link = stub(action.bot, "create_game_link")

        result = await action.guild_war.ensure_guild_war_convoke_link(game_data)

        decoy.verify(await create_link(ANY), times=0, ignore_extra_args=True)
        assert result is game_data

    async def test_ensure_guild_war_convoke_link_skips_when_convoke_returns_no_link(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(
            game_id=7,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        game_data.players = [create_mock_user(xid=100)]
        create_game_link_fake = stub(action.bot, "create_game_link")
        decoy.when(await create_game_link_fake(ANY), ignore_extra_args=True).then_return(
            GameLinkDetails(None, None)
        )
        attach = stub(services.games, "attach_game_link")

        result = await action.guild_war.ensure_guild_war_convoke_link(game_data)

        decoy.verify(await attach(ANY, ANY), times=0, ignore_extra_args=True)
        assert result is game_data
        assert result.game_link is None

    async def test_execute_opens_convoke_table_for_pending_guild_war(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(
            game_id=9,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            war_title="Dads vs Chill",
        )
        game_data.players = [create_mock_user(xid=100)]
        opened = create_mock_game(
            game_id=9,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            game_link="https://convoke.games/en/play/war",
        )
        opened.players = game_data.players
        resolve_guild_war_fake = stub(action.guild_war, "resolve_guild_war")
        decoy.when(
            await resolve_guild_war_fake(ANY, service=ANY, seats=ANY, locale=ANY),
            ignore_extra_args=True,
        ).then_return(
            (
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "Dads vs Chill",
                GameService.CONVOKE.value,
                4,
            )
        )
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(0)
        upsert_game_fake = stub(action, "upsert_game")
        decoy.when(
            await upsert_game_fake(author_xid=ANY, friend_xids=ANY, criteria=ANY),
            ignore_extra_args=True,
        ).then_return((True, game_data))
        ensure_link = stub(action.guild_war, "ensure_guild_war_convoke_link")
        decoy.when(await ensure_link(game_data)).then_return(opened)
        embed_stub = stub(action.game_posts, "handle_embed_creation")

        await action.execute(guild_war="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        # The new post is built from the game with its Convoke table already open.
        decoy.verify(await embed_stub(opened, new=True, origin=False), times=1)

    async def test_execute_skips_opening_table_when_link_already_exists(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        game_data = create_mock_game(
            game_id=9,
            war_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            war_title="Dads vs Chill",
            game_link="https://convoke.games/en/play/war",
        )
        game_data.players = [create_mock_user(xid=100)]
        resolve_guild_war_fake = stub(action.guild_war, "resolve_guild_war")
        decoy.when(
            await resolve_guild_war_fake(ANY, service=ANY, seats=ANY, locale=ANY),
            ignore_extra_args=True,
        ).then_return(
            (
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "Dads vs Chill",
                GameService.CONVOKE.value,
                4,
            )
        )
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(0)
        upsert_game_fake = stub(action, "upsert_game")
        decoy.when(
            await upsert_game_fake(author_xid=ANY, friend_xids=ANY, criteria=ANY),
            ignore_extra_args=True,
        ).then_return((True, game_data))
        create_link = stub(action.bot, "create_game_link")
        handle_embed_creation_fake = stub(action.game_posts, "handle_embed_creation")
        decoy.when(
            await handle_embed_creation_fake(ANY, new=ANY, origin=ANY),
            ignore_extra_args=True,
        ).then_return(game_data)

        await action.execute(guild_war="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        decoy.verify(await create_link(ANY), times=0, ignore_extra_args=True)

    async def test_create_initial_post_success(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _create_initial_post adds post on success."""
        mock_message = decoy.mock(cls=discord.Message)
        mock_message.id = 11111
        mock_embed = decoy.mock(cls=discord.Embed)
        game_data = create_mock_game(game_id=1)

        safe_followup_channel_fake = stub(game_posts, "safe_followup_channel")
        decoy.when(await safe_followup_channel_fake(ANY), ignore_extra_args=True).then_return(
            mock_message
        )
        add_post_stub = stub(services.games, "add_post")
        decoy.when(await add_post_stub(ANY, ANY, ANY, ANY), ignore_extra_args=True).then_return(
            game_data
        )

        await action.game_posts.create_initial_post(game_data, mock_embed)

        assert action.guild
        assert action.channel
        decoy.verify(
            await add_post_stub(game_data, action.guild.id, action.channel.id, 11111),
            times=1,
        )

    async def test_create_initial_post_followup_fails(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _create_initial_post does not add post when followup fails."""
        mock_embed = decoy.mock(cls=discord.Embed)
        game_data = create_mock_game(game_id=1)

        safe_followup_channel_fake = stub(game_posts, "safe_followup_channel")
        decoy.when(await safe_followup_channel_fake(ANY), ignore_extra_args=True).then_return(None)
        add_post_stub = stub(services.games, "add_post")

        await action.game_posts.create_initial_post(game_data, mock_embed)

        decoy.verify(await add_post_stub(ANY, ANY, ANY, ANY), times=0, ignore_extra_args=True)

    async def test_handle_embed_creation_different_channel(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_embed_creation fetches channel when post is in different channel."""
        mock_channel = decoy.mock(cls=discord.TextChannel)
        mock_message = decoy.mock(cls=discord.PartialMessage)

        game_data = create_mock_game(game_id=1)
        # Add a post to the game data (different from action.guild.id)
        game_data.posts = [create_test_post()]

        safe_fetch_text_channel_fake = stub(game_posts, "safe_fetch_text_channel")
        decoy.when(
            await safe_fetch_text_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_channel)
        safe_get_partial_message_fake = stub(game_posts, "safe_get_partial_message")
        decoy.when(
            safe_get_partial_message_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_message)
        update_stub = stub(game_posts, "safe_update_embed")
        decoy.when(await update_stub(ANY), ignore_extra_args=True).then_return(True)

        await action.game_posts.handle_embed_creation(game_data, new=False, origin=True)

        decoy.verify(await update_stub(ANY, embed=matchers.IsA(discord.Embed), view=ANY), times=1)

    async def test_handle_embed_creation_origin_post_updated(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test _handle_embed_creation updates origin post successfully."""
        mock_channel = decoy.mock(cls=discord.TextChannel)
        mock_channel.id = 88888
        mock_message = decoy.mock(cls=discord.Message)
        mock_message.id = 77777

        mock_guild = decoy.mock(cls=discord.Guild)
        mock_guild.id = 99999

        game_data = create_mock_game(game_id=1)
        game_data.posts = [create_test_post()]

        monkeypatch.setattr(action.interaction, "message", mock_message)
        monkeypatch.setattr(action, "channel", mock_channel)
        monkeypatch.setattr(action, "guild", mock_guild)
        origin_stub = stub(game_posts, "safe_update_embed_origin")
        decoy.when(await origin_stub(ANY), ignore_extra_args=True).then_return(True)
        update_stub = stub(game_posts, "safe_update_embed")

        await action.game_posts.handle_embed_creation(game_data, new=False, origin=True)

        decoy.verify(
            await origin_stub(
                action.interaction,
                content=ANY,
                embed=matchers.IsA(discord.Embed),
                view=ANY,
            ),
            times=1,
        )
        decoy.verify(await update_stub(ANY), times=0, ignore_extra_args=True)

    async def test_handle_embed_creation_origin_update_fails(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test _handle_embed_creation falls back when origin update fails."""
        mock_channel = decoy.mock(cls=discord.TextChannel)
        mock_channel.id = 88888
        mock_message = decoy.mock(cls=discord.Message)
        mock_message.id = 77777
        mock_partial_message = decoy.mock(cls=discord.PartialMessage)

        mock_guild = decoy.mock(cls=discord.Guild)
        mock_guild.id = 99999

        game_data = create_mock_game(game_id=1)
        game_data.posts = [create_test_post()]

        monkeypatch.setattr(action.interaction, "message", mock_message)
        monkeypatch.setattr(action, "channel", mock_channel)
        monkeypatch.setattr(action, "guild", mock_guild)
        safe_update_embed_origin_fake = stub(game_posts, "safe_update_embed_origin")
        decoy.when(await safe_update_embed_origin_fake(ANY), ignore_extra_args=True).then_return(
            False
        )
        safe_get_partial_message_fake = stub(game_posts, "safe_get_partial_message")
        decoy.when(
            safe_get_partial_message_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_partial_message)
        update_stub = stub(game_posts, "safe_update_embed")
        decoy.when(await update_stub(ANY), ignore_extra_args=True).then_return(True)

        await action.game_posts.handle_embed_creation(game_data, new=False, origin=True)

        decoy.verify(await update_stub(ANY, embed=matchers.IsA(discord.Embed), view=ANY), times=1)

    async def test_handle_embed_creation_channel_not_found(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_embed_creation skips when channel not found."""
        game_data = create_mock_game(game_id=1)
        game_data.posts = [create_test_post()]

        safe_fetch_text_channel_fake = stub(game_posts, "safe_fetch_text_channel")
        decoy.when(
            await safe_fetch_text_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(None)
        update_stub = stub(game_posts, "safe_update_embed")

        await action.game_posts.handle_embed_creation(game_data, new=False, origin=True)

        decoy.verify(await update_stub(ANY), times=0, ignore_extra_args=True)

    async def test_handle_embed_creation_message_not_found(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_embed_creation skips when message not found."""
        mock_channel = decoy.mock(cls=discord.TextChannel)

        game_data = create_mock_game(game_id=1)
        game_data.posts = [create_test_post()]

        safe_fetch_text_channel_fake = stub(game_posts, "safe_fetch_text_channel")
        decoy.when(
            await safe_fetch_text_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_channel)
        safe_get_partial_message_fake = stub(game_posts, "safe_get_partial_message")
        decoy.when(
            safe_get_partial_message_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(None)
        update_stub = stub(game_posts, "safe_update_embed")

        await action.game_posts.handle_embed_creation(game_data, new=False, origin=True)

        decoy.verify(await update_stub(ANY), times=0, ignore_extra_args=True)

    async def test_handle_embed_creation_update_fails(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_embed_creation continues when update fails."""
        mock_channel = decoy.mock(cls=discord.TextChannel)
        mock_message = decoy.mock(cls=discord.PartialMessage)

        game_data = create_mock_game(game_id=1)
        game_data.posts = [create_test_post()]
        safe_fetch_text_channel_fake = stub(game_posts, "safe_fetch_text_channel")
        decoy.when(
            await safe_fetch_text_channel_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_channel)
        safe_get_partial_message_fake = stub(game_posts, "safe_get_partial_message")
        decoy.when(
            safe_get_partial_message_fake(ANY, ANY, ANY),
            ignore_extra_args=True,
        ).then_return(mock_message)
        # Update returns False, meaning it failed
        safe_update_embed_fake = stub(game_posts, "safe_update_embed")
        decoy.when(await safe_update_embed_fake(ANY), ignore_extra_args=True).then_return(False)

        # Should not raise an exception, just continue
        await action.game_posts.handle_embed_creation(game_data, new=False, origin=True)

    async def test_reply_found_embed_no_jump_link(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _reply_found_embed when no jump link for current guild."""
        game_data = create_mock_game(game_id=123)
        game_data.posts = []  # No posts = no jump links

        followup_stub = stub(game_posts, "safe_followup_channel")

        await action.game_posts.reply_game_embed(game_data, started=False)

        # Check the embed description contains the game ID
        embed = matchers.ValueCaptor[discord.Embed]()
        decoy.verify(await followup_stub(action.interaction, embed=embed.matcher), times=1)
        embed_value = captured(embed, discord.Embed)
        assert embed_value.description is not None
        assert "SB123" in embed_value.description

    async def test_reply_force_start_embed_no_jump_link(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test reply_force_start_embed when no jump link for current guild."""
        game_data = create_mock_game(game_id=456)
        game_data.posts = []  # No posts = no jump links

        followup_stub = stub(game_posts, "safe_followup_channel")

        await action.game_posts.reply_game_embed(game_data, started=True)

        # Check the embed description contains the game ID and the right message
        embed = matchers.ValueCaptor[discord.Embed]()
        decoy.verify(await followup_stub(action.interaction, embed=embed.matcher), times=1)
        embed_value = captured(embed, discord.Embed)
        assert embed_value.description is not None
        assert "SB456" in embed_value.description
        assert "started" in embed_value.description

    async def test_handle_direct_messages_with_pin(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_direct_messages sends DMs with mythic track link when PIN exists."""
        mock_user = decoy.mock(cls=discord.User)

        game_data = create_mock_game(game_id=1)
        game_data.players = [create_mock_user(xid=123, name="TestPlayer")]
        game_data.player_pins = {123: "ABC123"}

        # Set up mythic_track emoji in bot's emojis_cache
        mt_emoji = decoy.mock(cls=discord.Emoji)
        mt_emoji.name = "mythic_track"
        action.bot.emojis_cache = [mt_emoji]

        safe_fetch_user_fake = stub(game_start, "safe_fetch_user")
        decoy.when(await safe_fetch_user_fake(ANY, ANY), ignore_extra_args=True).then_return(
            mock_user
        )
        send_stub = stub(game_start, "safe_send_user")
        give_awards_fake = stub(services.awards, "give_awards")
        decoy.when(await give_awards_fake(ANY, ANY), ignore_extra_args=True).then_return({})

        await action.game_start.handle_direct_messages(game_data)

        # Verify Mythic Track link was added to description
        embed = matchers.ValueCaptor[discord.Embed]()
        decoy.verify(await send_stub(mock_user, embed=embed.matcher), times=1)
        embed_value = captured(embed, discord.Embed)
        assert embed_value.description is not None
        assert "Mythic Track" in embed_value.description

    async def test_handle_direct_messages_with_pin_no_mythic_track_emoji(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_direct_messages sends DMs with mythic track link but no emoji prefix."""
        mock_user = decoy.mock(cls=discord.User)

        game_data = create_mock_game(game_id=1)
        game_data.players = [create_mock_user(xid=123, name="TestPlayer")]
        game_data.player_pins = {123: "ABC123"}

        # No mythic_track emoji in bot's emojis_cache
        action.bot.emojis_cache = []

        safe_fetch_user_fake = stub(game_start, "safe_fetch_user")
        decoy.when(await safe_fetch_user_fake(ANY, ANY), ignore_extra_args=True).then_return(
            mock_user
        )
        send_stub = stub(game_start, "safe_send_user")
        give_awards_fake = stub(services.awards, "give_awards")
        decoy.when(await give_awards_fake(ANY, ANY), ignore_extra_args=True).then_return({})

        await action.game_start.handle_direct_messages(game_data)

        # Verify Mythic Track link was added to description
        embed = matchers.ValueCaptor[discord.Embed]()
        decoy.verify(await send_stub(mock_user, embed=embed.matcher), times=1)
        embed_value = captured(embed, discord.Embed)
        assert embed_value.description is not None
        assert "Mythic Track" in embed_value.description
        # Verify the description contains "[Mythic Track]" (no emoji prefix)
        assert "[Mythic Track]" in embed_value.description

    async def test_handle_direct_messages_award_to_unfetched_player(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_direct_messages warns when award goes to unfetched player."""
        game_data = create_mock_game(game_id=1)
        game_data.players = [create_mock_user(xid=123, name="TestPlayer")]
        game_data.player_pins = {123: None}

        # Player cannot be fetched
        safe_fetch_user_fake = stub(game_start, "safe_fetch_user")
        decoy.when(await safe_fetch_user_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        stub(game_start, "safe_send_user")

        # Award for unfetched player
        new_award = NewAward(role="SomeRole", message="Congrats!", remove=False)
        give_awards_fake = stub(services.awards, "give_awards")
        decoy.when(await give_awards_fake(ANY, ANY), ignore_extra_args=True).then_return(
            {123: [new_award]}
        )
        followup_stub = stub(game_start, "safe_followup_channel")

        await action.game_start.handle_direct_messages(game_data)

        # The award can't be given, and the player can't be DMed.
        decoy.verify(
            await followup_stub(action.interaction, "Unable to give role SomeRole to user <@123>"),
            await followup_stub(
                action.interaction,
                "Unable to send Direct Messages to some players: <@!123>",
            ),
        )

    async def test_handle_direct_messages_award_success(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test _handle_direct_messages gives awards to fetched players."""
        mock_user = decoy.mock(cls=discord.User)

        game_data = create_mock_game(game_id=1)
        game_data.players = [create_mock_user(xid=123, name="TestPlayer")]
        game_data.player_pins = {123: None}

        safe_fetch_user_fake = stub(game_start, "safe_fetch_user")
        decoy.when(await safe_fetch_user_fake(ANY, ANY), ignore_extra_args=True).then_return(
            mock_user
        )
        send_stub = stub(game_start, "safe_send_user")
        add_role_stub = stub(game_start, "safe_add_role")

        # Award for fetched player
        new_award = NewAward(role="SomeRole", message="Congrats!", remove=False)
        give_awards_fake = stub(services.awards, "give_awards")
        decoy.when(await give_awards_fake(ANY, ANY), ignore_extra_args=True).then_return(
            {123: [new_award]}
        )

        await action.game_start.handle_direct_messages(game_data)

        # Should give role
        decoy.verify(await add_role_stub(ANY, ANY, ANY), times=1, ignore_extra_args=True)
        # Should send the game DM, then the award message
        decoy.verify(await send_stub(mock_user, embed=matchers.IsA(discord.Embed)), times=1)
        decoy.verify(await send_stub(mock_user, "Congrats!"), times=1)

    async def test_execute_start_no_guild(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        """Test execute_start when guild is None."""
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action, "guild", None)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        fake = stub(lfg_action, "safe_send_user")

        await action.execute_start()

        decoy.verify(
            await fake(
                discord_user,
                "Please run this command in the same channel as your game.",
                ephemeral=True,
            ),
            times=1,
        )

    async def test_execute_start_no_channel(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
        monkeypatch: pytest.MonkeyPatch,
        user: User,
    ) -> None:
        """Test execute_start when channel is None."""
        discord_user = mock_discord_object(decoy, user)
        monkeypatch.setattr(action, "channel", None)
        monkeypatch.setattr(action.interaction, "user", discord_user)
        fake = stub(lfg_action, "safe_send_user")

        await action.execute_start()

        decoy.verify(
            await fake(
                discord_user,
                "Please run this command in the same channel as your game.",
                ephemeral=True,
            ),
            times=1,
        )

    async def test_execute_start_not_waiting(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test execute_start when user is not in a pending game."""
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        fake = stub(lfg_action, "safe_followup_channel")

        await action.execute_start()

        decoy.verify(
            await fake(
                action.interaction,
                "You're not in a pending game in this channel.",
                ephemeral=True,
            ),
            times=1,
        )

    async def test_execute_start_blocked_with_a_single_player(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """A game of one has no opponent, and the link services reject a one seat table."""
        game_data = create_mock_game(game_id=42)
        game_data.players = [create_mock_user(xid=100, name="Player1")]

        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(game_data)
        fake = stub(lfg_action, "safe_followup_channel")
        shrink_stub = stub(services.games, "shrink_game")
        ready_stub = stub(action.game_start, "make_game_ready")

        await action.execute_start()

        decoy.verify(
            await fake(
                action.interaction,
                "You need at least one other player before you can start a game.",
                ephemeral=True,
            ),
            times=1,
        )
        decoy.verify(await shrink_stub(ANY), times=0, ignore_extra_args=True)
        decoy.verify(await ready_stub(ANY, ANY), times=0, ignore_extra_args=True)

    async def test_execute_start_blocked_with_no_players(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """An empty queue is stopped by the same guard rather than shrinking to zero seats."""
        game_data = create_mock_game(game_id=42)
        game_data.players = []

        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(game_data)
        fake = stub(lfg_action, "safe_followup_channel")
        shrink_stub = stub(services.games, "shrink_game")

        await action.execute_start()

        decoy.verify(await fake(ANY), times=1, ignore_extra_args=True)
        decoy.verify(await shrink_stub(ANY), times=0, ignore_extra_args=True)

    async def test_execute_start_happy_path(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Test execute_start when user is in a pending game (success path)."""
        game_data = create_mock_game(game_id=42)
        # Add some players to the game data
        game_data.players = [
            create_mock_user(xid=100, name="Player1"),
            create_mock_user(xid=200, name="Player2"),
        ]

        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(game_data)
        # Each step is stubbed only for the arguments it should get, so the DMs at the end
        # only go out for this game if every step before them was called correctly.
        shrink_game = stub(services.games, "shrink_game")
        decoy.when(await shrink_game(game_data)).then_return(game_data)
        mock_suggestion = VoiceChannelSuggestion(already_picked=None, random_empty=None)
        player_xids = matchers.ValueCaptor[list[int]]()
        make_game_ready = stub(action.game_start, "make_game_ready")
        decoy.when(
            await make_game_ready(game_data, player_xids.matcher),
            ignore_extra_args=True,
        ).then_return((game_data, mock_suggestion))
        voice_stub = stub(action.game_start, "handle_voice_creation")
        decoy.when(await voice_stub(game_data, action.interaction.guild_id)).then_return(game_data)
        embed_stub = stub(action.game_posts, "handle_embed_creation")
        decoy.when(
            await embed_stub(game_data, new=False, origin=False, force_start=True),
            ignore_extra_args=True,
        ).then_return(game_data)
        dm_stub = stub(action.game_start, "handle_direct_messages")

        await action.execute_start()

        player_xids_value = captured(player_xids, list)
        assert set(player_xids_value) == {100, 200}
        decoy.verify(
            await dm_stub(game_data, suggested_vc=mock_suggestion, rematch=False),
            times=1,
        )

    async def test_block_if_no_player_linked_non_playgroup_service(
        self,
        action: LookingForGameAction,
    ) -> None:
        """Returns False for services other than Playgroup Live."""
        game_data = create_mock_game(service=GameService.CONVOKE.value)
        assert await action.block_if_no_player_linked(game_data) is False

    async def test_block_if_no_player_linked_with_linked_player(
        self,
        action: LookingForGameAction,
    ) -> None:
        """Returns False when at least one player is linked to Playgroup Live."""
        game_data = create_mock_game(service=GameService.PLAYGROUP_LIVE.value)
        host = create_mock_user(xid=100)
        host.playgroup_user_id = 42
        game_data.players = [host]
        assert await action.block_if_no_player_linked(game_data) is False

    async def test_block_if_no_player_linked_no_linked_player(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Returns True and sends followup when no player is linked to Playgroup Live."""
        game_data = create_mock_game(service=GameService.PLAYGROUP_LIVE.value)
        game_data.players = [create_mock_user(xid=100)]
        fake = stub(lfg_action, "safe_followup_channel")

        assert await action.block_if_no_player_linked(game_data) is True

        decoy.verify(
            await fake(
                action.interaction,
                "To use Playgroup Live, at least one player must link their account. "
                "Run `/playgroup link` and try again.",
            ),
            times=1,
        )

    async def test_execute_start_blocked_when_no_player_linked(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """execute_start returns early when no player is linked to Playgroup Live."""
        game_data = create_mock_game(service=GameService.PLAYGROUP_LIVE.value)
        game_data.players = [create_mock_user(xid=100)]

        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(game_data)
        stub(lfg_action, "safe_followup_channel")
        shrink_stub = stub(services.games, "shrink_game")

        await action.execute_start()

        decoy.verify(await shrink_stub(ANY), times=0, ignore_extra_args=True)

    async def test_execute_blocked_when_fully_seated_and_no_player_linked(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        """Execute returns early when game is fully seated but no player is linked."""
        game_data = create_mock_game(service=GameService.PLAYGROUP_LIVE.value, seats=1)
        game_data.players = [create_mock_user(xid=100)]
        assert game_data.fully_seated

        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(0)
        upsert_game_fake = stub(action, "upsert_game")
        decoy.when(
            await upsert_game_fake(author_xid=ANY, friend_xids=ANY, criteria=ANY),
            ignore_extra_args=True,
        ).then_return((True, game_data))
        stub(lfg_action, "safe_followup_channel")
        other_ids_stub = stub(services.games, "other_game_ids")

        await action.execute(format=GameFormat.COMMANDER.value)

        decoy.verify(await other_ids_stub(ANY), times=0, ignore_extra_args=True)


WAR_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
WAR_TITLE = "Summer Clash"
LIVE_WAR: LiveGuildWar = {
    "id": WAR_ID,
    "title": WAR_TITLE,
    "slug": "summer-clash",
    "status": "active",
}


@pytest.mark.asyncio
class TestLookingForGameActionGuildWar:
    """Covers the Convoke Guild War branches of `/war`."""

    async def patch_resolver(
        self,
        decoy: Decoy,
        stub: Stub,
        war: LiveGuildWar | None,
    ) -> Callable[[str], Awaitable[LiveGuildWar | None]]:
        resolver = stub(convoke, "resolve_live_guild_war")
        decoy.when(await resolver(ANY), ignore_extra_args=True).then_return(war)
        return resolver

    async def test_no_war_passes_options_through_untouched(
        self,
        action: LookingForGameAction,
    ) -> None:
        # `/lfg` still goes through this method, so a request with no war must be
        # returned exactly as it came in.
        result = await action.guild_war.resolve_guild_war(
            None,
            service=GameService.X_MAGE.value,
            seats=6,
            locale="en",
        )
        assert result == (None, None, GameService.X_MAGE.value, 6)

    async def test_join_button_ignores_the_war(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # Joining an existing game resolves the war from the game itself, so a click
        # must not re-resolve it (which would cost a Convoke round-trip per click).
        resolver = await self.patch_resolver(decoy, stub, LIVE_WAR)
        reject_if_busy_fake = stub(action, "reject_if_busy")
        decoy.when(await reject_if_busy_fake(ANY, origin=ANY), ignore_extra_args=True).then_return(
            False
        )
        join_game_fake = stub(action, "join_game")
        decoy.when(await join_game_fake(ANY), ignore_extra_args=True).then_return(None)

        await action.execute(message_xid=12345, guild_war=WAR_ID)

        decoy.verify(await resolver(WAR_ID), times=0)

    async def test_resolves_a_live_war_and_forces_convoke(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        await self.patch_resolver(decoy, stub, LIVE_WAR)
        result = await action.guild_war.resolve_guild_war(
            WAR_ID,
            service=None,
            seats=None,
            locale="en",
        )
        assert result == (
            WAR_ID,
            WAR_TITLE,
            GameService.CONVOKE.value,
            convoke.DEFAULT_WAR_SEATS,
        )

    async def test_the_war_id_is_stripped_before_resolving(
        self,
        action: LookingForGameAction,
        stub: Stub,
        decoy: Decoy,
    ) -> None:
        resolver = await self.patch_resolver(decoy, stub, LIVE_WAR)
        await action.guild_war.resolve_guild_war(
            f"  {WAR_ID}  ",
            service=None,
            seats=None,
            locale="en",
        )
        decoy.verify(await resolver(WAR_ID), times=1)

    async def test_explicit_seats_are_kept(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        await self.patch_resolver(decoy, stub, LIVE_WAR)
        result = await action.guild_war.resolve_guild_war(
            WAR_ID,
            service=None,
            seats=6,
            locale="en",
        )
        assert result is not None
        assert result[3] == 6

    async def test_a_war_is_always_a_convoke_game(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        # Guild Wars only exist on Convoke, so any other service is overridden rather
        # than rejected — `/war` never offers the choice in the first place.
        await self.patch_resolver(decoy, stub, LIVE_WAR)

        result = await action.guild_war.resolve_guild_war(
            WAR_ID,
            service=GameService.X_MAGE.value,
            seats=None,
            locale="en",
        )

        assert result is not None
        assert result[2] == GameService.CONVOKE.value

    async def test_an_unknown_war_is_rejected(
        self,
        action: LookingForGameAction,
        stub: Stub,
        decoy: Decoy,
    ) -> None:
        reply = stub(guild_war, "safe_followup_channel")
        await self.patch_resolver(decoy, stub, None)

        result = await action.guild_war.resolve_guild_war(
            "not-a-real-war",
            service=None,
            seats=None,
            locale="en",
        )

        assert result is None
        message = matchers.ValueCaptor[str]()
        decoy.verify(await reply(action.interaction, message.matcher), ignore_extra_args=True)
        message_value = captured(message, str)
        assert "not available" in message_value

    @pytest.mark.parametrize(
        "seats",
        [
            pytest.param(convoke.MIN_WAR_SEATS - 1, id="below_min"),
            pytest.param(convoke.MAX_WAR_SEATS + 1, id="above_max"),
        ],
    )
    async def test_out_of_range_seats_are_rejected(
        self,
        action: LookingForGameAction,
        stub: Stub,
        seats: int,
        decoy: Decoy,
    ) -> None:
        reply = stub(guild_war, "safe_followup_channel")
        await self.patch_resolver(decoy, stub, LIVE_WAR)

        result = await action.guild_war.resolve_guild_war(
            WAR_ID,
            service=None,
            seats=seats,
            locale="en",
        )

        assert result is None
        # The bounds in the message come from the constants, so they can not drift.
        message = matchers.ValueCaptor[str]()
        decoy.verify(await reply(action.interaction, message.matcher), ignore_extra_args=True)
        message_value = captured(message, str)
        assert f"between {convoke.MIN_WAR_SEATS} and {convoke.MAX_WAR_SEATS} seats" in message_value

    async def test_boundary_seats_are_accepted(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        await self.patch_resolver(decoy, stub, LIVE_WAR)
        for seats in (convoke.MIN_WAR_SEATS, convoke.MAX_WAR_SEATS):
            result = await action.guild_war.resolve_guild_war(
                WAR_ID,
                service=None,
                seats=seats,
                locale="en",
            )
            assert result is not None, seats

    async def test_execute_stops_before_creating_a_game_for_an_unknown_war(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        stub(lfg_action, "safe_followup_channel")
        await self.patch_resolver(decoy, stub, None)
        upsert = stub(action, "upsert_game")

        await action.execute(guild_war="not-a-real-war")

        decoy.verify(
            await upsert(author_xid=ANY, friend_xids=ANY, criteria=ANY),
            times=0,
            ignore_extra_args=True,
        )

    async def test_execute_passes_war_fields_to_upsert(
        self,
        action: LookingForGameAction,
        decoy: Decoy,
        stub: Stub,
    ) -> None:
        await self.patch_resolver(decoy, stub, LIVE_WAR)
        stub(lfg_action, "safe_followup_channel")
        is_waiting_fake = stub(services.users, "is_waiting")
        decoy.when(await is_waiting_fake(ANY, ANY), ignore_extra_args=True).then_return(None)
        pending_games_fake = stub(services.users, "pending_games")
        decoy.when(await pending_games_fake(ANY), ignore_extra_args=True).then_return(0)
        upsert = stub(action, "upsert_game")
        decoy.when(
            await upsert(author_xid=ANY, friend_xids=ANY, criteria=ANY),
            ignore_extra_args=True,
        ).then_return((False, None))

        await action.execute(guild_war=WAR_ID)

        criteria = matchers.ValueCaptor[GameCriteria]()
        decoy.verify(await upsert(author_xid=ANY, friend_xids=ANY, criteria=criteria.matcher))
        criteria_value = captured(criteria, GameCriteria)
        assert criteria_value.war_id == WAR_ID
        assert criteria_value.war_title == WAR_TITLE
