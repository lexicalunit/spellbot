from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
import pytest_asyncio

from spellbot.actions import LookingForGameAction
from spellbot.enums import GameBracket, GameFormat, GameService
from spellbot.operations import VoiceChannelSuggestion
from spellbot.services.awards import NewAward
from spellbot.settings import settings
from tests.mocks import mock_discord_object

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.models import GameDict, GuildDict, User

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def action(bot: SpellBot, interaction: discord.Interaction) -> LookingForGameAction:
    async with LookingForGameAction.create(bot, interaction) as action:
        return action


@pytest.mark.asyncio
class TestLookingForGameAction:
    async def test_get_service(self, action: LookingForGameAction) -> None:
        assert await action.get_service(GameService.X_MAGE.value) == GameService.X_MAGE.value

    async def test_get_service_fallback_channel_data(self, action: LookingForGameAction) -> None:
        action.channel_data["default_service"] = GameService.X_MAGE
        assert await action.get_service(None) == GameService.X_MAGE.value

    async def test_get_service_fallback_default(self, action: LookingForGameAction) -> None:
        action.channel_data["default_service"] = None  # type: ignore
        assert await action.get_service(None) == GameService.CONVOKE.value

    async def test_get_format(self, action: LookingForGameAction) -> None:
        assert await action.get_format(GameFormat.PAUPER.value) == GameFormat.PAUPER.value

    async def test_get_format_fallback_channel_data(self, action: LookingForGameAction) -> None:
        action.channel_data["default_format"] = GameFormat.PAUPER
        assert await action.get_format(None) == GameFormat.PAUPER.value

    async def test_get_format_fallback_default(self, action: LookingForGameAction) -> None:
        action.channel_data["default_format"] = None  # type: ignore
        assert await action.get_format(None) == GameFormat.COMMANDER.value

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
    async def test_get_bracket(
        self,
        action: LookingForGameAction,
        format: int,
        bracket: int,
        actual: int,
    ) -> None:
        assert await action.get_bracket(format, bracket) == actual

    async def test_get_bracket_with_channel_default(
        self,
        action: LookingForGameAction,
    ) -> None:
        action.channel_data["default_bracket"] = GameBracket.BRACKET_1
        assert await action.get_bracket(None, None) == GameBracket.BRACKET_1.value

    async def test_execute_in_non_guild_channel(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        discord_user = mock_discord_object(user)
        mocker.patch.object(action, "guild", None)
        mocker.patch.object(action.interaction, "user", discord_user)
        stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        result = await action.execute()

        assert result is None
        stub.assert_called_once_with(
            discord_user,
            "Sorry, that command is not supported in this context.",
        )

    async def test_execute_rematch_no_guild(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        """Test execute_rematch when guild is None."""
        discord_user = mock_discord_object(user)
        mocker.patch.object(action, "guild", None)
        mocker.patch.object(action.interaction, "user", discord_user)
        stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        await action.execute_rematch()

        stub.assert_called_once_with(
            discord_user,
            "Please run this command in the same channel as your last played game.",
        )

    async def test_execute_rematch_no_channel(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        """Test execute_rematch when channel is None."""
        discord_user = mock_discord_object(user)
        mocker.patch.object(action, "channel", None)
        mocker.patch.object(action.interaction, "user", discord_user)
        stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        await action.execute_rematch()

        stub.assert_called_once_with(
            discord_user,
            "Please run this command in the same channel as your last played game.",
        )

    async def test_execute_rematch_pending_games(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test execute_rematch when user already has pending games."""
        mocker.patch.object(action.services.users, "pending_games", AsyncMock(return_value=1))
        stub = mocker.patch("spellbot.actions.lfg_action.safe_followup_channel", AsyncMock())

        await action.execute_rematch()

        stub.assert_called_once_with(
            action.interaction,
            "You're already in a pending game, leave that one first.",
        )

    async def test_execute_rematch_no_last_game(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test execute_rematch when user has no last game."""
        mocker.patch.object(action.services.users, "pending_games", AsyncMock(return_value=0))
        mocker.patch.object(action.services.games, "select_last_game", AsyncMock(return_value=None))
        stub = mocker.patch("spellbot.actions.lfg_action.safe_followup_channel", AsyncMock())

        await action.execute_rematch()

        stub.assert_called_once_with(
            action.interaction,
            "You have not played a game in this guild yet.",
        )

    async def test_execute_already_waiting_origin(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        """Test execute when user is already waiting from button (origin=True)."""
        discord_user = mock_discord_object(user)
        mocker.patch.object(action.interaction, "user", discord_user)
        mocker.patch.object(action.services.users, "is_waiting", AsyncMock(return_value=True))
        stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        # message_xid makes origin=True
        await action.execute(message_xid=12345)

        stub.assert_called_once_with(
            discord_user,
            "You're already in a game in this channel.",
        )

    async def test_execute_too_many_pending_games_origin(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
        user: User,
    ) -> None:
        """Test execute when user has too many pending games (from button)."""
        discord_user = mock_discord_object(user)
        mocker.patch.object(action.interaction, "user", discord_user)
        mocker.patch.object(action.services.users, "is_waiting", AsyncMock(return_value=False))
        mocker.patch.object(
            action.services.users,
            "pending_games",
            AsyncMock(return_value=settings.MAX_PENDING_GAMES),
        )
        stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        # message_xid makes origin=True
        await action.execute(message_xid=12345)

        stub.assert_called_once_with(
            discord_user,
            "You're in too many pending games to join another one at this time.",
        )

    async def test_execute_too_many_pending_games_non_origin(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test execute when user has too many pending games (from slash command)."""
        mocker.patch.object(action.services.users, "is_waiting", AsyncMock(return_value=False))
        mocker.patch.object(
            action.services.users,
            "pending_games",
            AsyncMock(return_value=settings.MAX_PENDING_GAMES),
        )
        stub = mocker.patch("spellbot.actions.lfg_action.safe_followup_channel", AsyncMock())

        # No message_xid means origin=False (slash command)
        result = await action.execute()

        assert result is None
        stub.assert_called_once_with(
            action.interaction,
            "You're in too many pending games to join another one at this time.",
        )

    async def test_update_other_game_posts_no_games(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _update_other_game_posts returns early when no other game IDs."""
        # Should return immediately without calling message_xids
        stub = mocker.patch.object(action.services.games, "message_xids", AsyncMock())
        await action._update_other_game_posts([])
        stub.assert_not_called()

    async def test_update_other_game_posts_with_games(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _update_other_game_posts updates embeds for other games."""
        game_data = {
            "channel_xid": 12345,
            "guild_xid": 67890,
        }
        mocker.patch.object(action.services.games, "message_xids", AsyncMock(return_value=[111]))
        mocker.patch.object(
            action.services.games,
            "select_by_message_xid",
            AsyncMock(return_value=game_data),
        )

        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)
        mock_embed = MagicMock(spec=discord.Embed)

        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_text_channel",
            AsyncMock(return_value=mock_channel),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_get_partial_message",
            return_value=mock_message,
        )
        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        update_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(return_value=True),
        )

        await action._update_other_game_posts([1])

        update_stub.assert_called_once()

    async def test_update_other_game_posts_no_data(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _update_other_game_posts skips when no game data found."""
        mocker.patch.object(action.services.games, "message_xids", AsyncMock(return_value=[111]))
        mocker.patch.object(
            action.services.games,
            "select_by_message_xid",
            AsyncMock(return_value=None),
        )

        update_stub = mocker.patch("spellbot.actions.lfg_action.safe_update_embed", AsyncMock())

        await action._update_other_game_posts([1])

        update_stub.assert_not_called()

    async def test_update_other_game_posts_channel_not_found(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _update_other_game_posts skips when channel not found."""
        mocker.patch.object(action.services.games, "message_xids", AsyncMock(return_value=[111]))
        mocker.patch.object(
            action.services.games,
            "select_by_message_xid",
            AsyncMock(return_value={"channel_xid": 123, "guild_xid": 456}),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_text_channel",
            AsyncMock(return_value=None),
        )

        update_stub = mocker.patch("spellbot.actions.lfg_action.safe_update_embed", AsyncMock())

        await action._update_other_game_posts([1])

        update_stub.assert_not_called()

    async def test_ensure_users_exist_user_not_found(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test ensure_users_exist when user cannot be fetched."""
        mocker.patch("spellbot.actions.lfg_action.safe_fetch_user", AsyncMock(return_value=None))

        result = await action.ensure_users_exist([99999])

        assert result == []

    async def test_ensure_users_exist_excludes_self(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test ensure_users_exist excludes self when exclude_self=True."""
        self_id = action.interaction.user.id
        fetch_stub = mocker.patch("spellbot.actions.lfg_action.safe_fetch_user", AsyncMock())

        result = await action.ensure_users_exist([self_id], exclude_self=True)

        assert result == []
        fetch_stub.assert_not_called()

    async def test_handle_voice_creation_no_category(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_voice_creation returns when category not found."""
        mocker.patch.object(
            action.services.guilds,
            "should_voice_create",
            AsyncMock(return_value=True),
        )
        mocker.patch.object(
            action.services.guilds,
            "get_use_max_bitrate",
            AsyncMock(return_value=False),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_ensure_voice_category",
            AsyncMock(return_value=None),
        )
        voice_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_create_voice_channel",
            AsyncMock(),
        )

        await action._handle_voice_creation(12345)

        voice_stub.assert_not_called()

    async def test_handle_voice_creation_no_voice_channel(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_voice_creation returns when voice channel creation fails."""
        mock_category = MagicMock(spec=discord.CategoryChannel)
        mocker.patch.object(
            action.services.guilds,
            "should_voice_create",
            AsyncMock(return_value=True),
        )
        mocker.patch.object(
            action.services.guilds,
            "get_use_max_bitrate",
            AsyncMock(return_value=False),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_ensure_voice_category",
            AsyncMock(return_value=mock_category),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_create_voice_channel",
            AsyncMock(return_value=None),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value={"id": 1}))

        set_voice_stub = mocker.patch.object(action.services.games, "set_voice", AsyncMock())

        await action._handle_voice_creation(12345)

        set_voice_stub.assert_not_called()

    async def test_handle_voice_creation_with_invite(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_voice_creation creates voice invite when configured."""
        mock_category = MagicMock(spec=discord.CategoryChannel)
        mock_voice_channel = MagicMock(spec=discord.VoiceChannel)
        mock_voice_channel.id = 99999
        mock_invite = MagicMock(spec=discord.Invite)
        mock_invite.url = "https://discord.gg/invite"

        mocker.patch.object(
            action.services.guilds,
            "should_voice_create",
            AsyncMock(return_value=True),
        )
        mocker.patch.object(
            action.services.guilds,
            "get_use_max_bitrate",
            AsyncMock(return_value=False),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_ensure_voice_category",
            AsyncMock(return_value=mock_category),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_create_voice_channel",
            AsyncMock(return_value=mock_voice_channel),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_create_channel_invite",
            AsyncMock(return_value=mock_invite),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value={"id": 1}))

        # Enable voice invite
        action.channel_data["voice_invite"] = True

        set_voice_stub = mocker.patch.object(action.services.games, "set_voice", AsyncMock())

        await action._handle_voice_creation(12345)

        set_voice_stub.assert_called_once_with(
            voice_xid=99999,
            voice_invite_link="https://discord.gg/invite",
        )

    async def test_handle_voice_creation_without_invite(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_voice_creation without voice invite."""
        mock_category = MagicMock(spec=discord.CategoryChannel)
        mock_voice_channel = MagicMock(spec=discord.VoiceChannel)
        mock_voice_channel.id = 99999

        mocker.patch.object(
            action.services.guilds,
            "should_voice_create",
            AsyncMock(return_value=True),
        )
        mocker.patch.object(
            action.services.guilds,
            "get_use_max_bitrate",
            AsyncMock(return_value=False),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_ensure_voice_category",
            AsyncMock(return_value=mock_category),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_create_voice_channel",
            AsyncMock(return_value=mock_voice_channel),
        )
        invite_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_create_channel_invite",
            AsyncMock(),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value={"id": 1}))

        # voice_invite is False by default
        action.channel_data["voice_invite"] = False

        set_voice_stub = mocker.patch.object(action.services.games, "set_voice", AsyncMock())

        await action._handle_voice_creation(12345)

        invite_stub.assert_not_called()
        set_voice_stub.assert_called_once_with(
            voice_xid=99999,
            voice_invite_link=None,
        )

    async def test_handle_watched_players_no_mod_role(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_watched_players returns early when no mod role found."""
        # Create guild with no mod role
        mock_role = MagicMock(spec=discord.Role)
        mock_role.name = "Regular Role"
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.roles = [mock_role]
        mocker.patch.object(action.interaction, "guild", mock_guild)

        watch_stub = mocker.patch.object(action.services.games, "watch_notes", AsyncMock())

        await action._handle_watched_players([123])

        watch_stub.assert_not_called()

    async def test_handle_watched_players_no_watched_users(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_watched_players returns when no watched users."""
        # Create guild with mod role
        mock_role = MagicMock(spec=discord.Role)
        mock_role.name = f"{settings.MOD_PREFIX}Admin"
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.roles = [mock_role]
        mocker.patch.object(action.interaction, "guild", mock_guild)
        mocker.patch.object(action.services.games, "watch_notes", AsyncMock(return_value={}))

        send_stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        await action._handle_watched_players([123])

        send_stub.assert_not_called()

    async def test_handle_watched_players_sends_notification(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_watched_players sends notification to moderators."""
        mock_member = MagicMock(spec=discord.Member)

        # Create guild with mod role that has members
        mock_role = MagicMock(spec=discord.Role)
        mock_role.name = f"{settings.MOD_PREFIX}Admin"
        mock_role.members = [mock_member]
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.roles = [mock_role]
        mocker.patch.object(action.interaction, "guild", mock_guild)

        game_data = {
            "id": 1,
            "jump_links": {mock_guild.id: "https://discord.com/jump/1"},
        }
        mocker.patch.object(
            action.services.games,
            "watch_notes",
            AsyncMock(return_value={123: "suspicious"}),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))

        send_stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        await action._handle_watched_players([123])

        send_stub.assert_called_once()

    async def test_make_game_ready_with_voice_suggestion(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test make_game_ready calls safe_suggest_voice_channel when conditions are met."""
        game_data = cast(
            "GameDict",
            {
                "id": 1,
                "voice_xid": None,
                "voice_invite_link": None,
            },
        )
        action.guild_data = cast(
            "GuildDict",
            {
                "xid": 12345,
                "name": "Test Guild",
                "suggest_voice_category": "Voice Channels",
                "created_at": None,
                "updated_at": None,
                "banned": False,
                "motd": None,
                "show_links": True,
                "voice_create": False,
                "use_max_bitrate": False,
            },
        )

        mock_suggestion = VoiceChannelSuggestion(already_picked=None, random_empty=None)
        mocker.patch(
            "spellbot.actions.lfg_action.safe_suggest_voice_channel",
            return_value=mock_suggestion,
        )
        mocker.patch.object(
            action.bot,
            "create_game_link",
            AsyncMock(return_value=MagicMock(link="https://game.link", password=None)),
        )
        mocker.patch.object(action.services.games, "make_ready", AsyncMock(return_value=1))

        _, suggested_vc = await action.make_game_ready(game_data, [123, 456])

        assert suggested_vc == mock_suggestion

    async def test_create_initial_post_success(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _create_initial_post adds post on success."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 11111
        mock_embed = MagicMock(spec=discord.Embed)

        mocker.patch(
            "spellbot.actions.lfg_action.safe_followup_channel",
            AsyncMock(return_value=mock_message),
        )
        add_post_stub = mocker.patch.object(action.services.games, "add_post", AsyncMock())

        await action._create_initial_post(mock_embed)

        add_post_stub.assert_called_once()

    async def test_create_initial_post_followup_fails(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _create_initial_post does not add post when followup fails."""
        mock_embed = MagicMock(spec=discord.Embed)

        mocker.patch(
            "spellbot.actions.lfg_action.safe_followup_channel",
            AsyncMock(return_value=None),
        )
        add_post_stub = mocker.patch.object(action.services.games, "add_post", AsyncMock())

        await action._create_initial_post(mock_embed)

        add_post_stub.assert_not_called()

    async def test_handle_embed_creation_different_channel(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_embed_creation fetches channel when post is in different channel."""
        mock_embed = MagicMock(spec=discord.Embed)
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        game_data = {
            "posts": [
                {
                    "guild_xid": 99999,  # Different from action.guild.id
                    "channel_xid": 88888,
                    "message_xid": 77777,
                },
            ],
        }

        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_text_channel",
            AsyncMock(return_value=mock_channel),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_get_partial_message",
            return_value=mock_message,
        )
        update_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(return_value=True),
        )

        await action._handle_embed_creation(new=False, origin=True, fully_seated=False)

        update_stub.assert_called_once()

    async def test_handle_embed_creation_origin_post_updated(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_embed_creation updates origin post successfully."""
        mock_embed = MagicMock(spec=discord.Embed)
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 88888
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 77777

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 99999

        game_data = {
            "posts": [
                {
                    "guild_xid": 99999,
                    "channel_xid": 88888,
                    "message_xid": 77777,
                },
            ],
        }

        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch.object(action.interaction, "message", mock_message)
        mocker.patch.object(action, "channel", mock_channel)
        mocker.patch.object(action, "guild", mock_guild)
        origin_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed_origin",
            AsyncMock(return_value=True),
        )
        update_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(),
        )

        await action._handle_embed_creation(new=False, origin=True, fully_seated=False)

        origin_stub.assert_called_once()
        update_stub.assert_not_called()

    async def test_handle_embed_creation_origin_update_fails(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_embed_creation falls back when origin update fails."""
        mock_embed = MagicMock(spec=discord.Embed)
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 88888
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 77777
        mock_partial_message = MagicMock(spec=discord.PartialMessage)

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 99999

        game_data = {
            "posts": [
                {
                    "guild_xid": 99999,
                    "channel_xid": 88888,
                    "message_xid": 77777,
                },
            ],
        }

        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch.object(action.interaction, "message", mock_message)
        mocker.patch.object(action, "channel", mock_channel)
        mocker.patch.object(action, "guild", mock_guild)
        mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed_origin",
            AsyncMock(return_value=False),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_get_partial_message",
            return_value=mock_partial_message,
        )
        update_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(return_value=True),
        )

        await action._handle_embed_creation(new=False, origin=True, fully_seated=False)

        update_stub.assert_called_once()

    async def test_handle_embed_creation_channel_not_found(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_embed_creation skips when channel not found."""
        mock_embed = MagicMock(spec=discord.Embed)

        game_data = {
            "posts": [
                {
                    "guild_xid": 99999,  # Different from action.guild.id
                    "channel_xid": 88888,
                    "message_xid": 77777,
                },
            ],
        }

        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_text_channel",
            AsyncMock(return_value=None),
        )
        update_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(),
        )

        await action._handle_embed_creation(new=False, origin=True, fully_seated=False)

        update_stub.assert_not_called()

    async def test_handle_embed_creation_message_not_found(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_embed_creation skips when message not found."""
        mock_embed = MagicMock(spec=discord.Embed)
        mock_channel = MagicMock(spec=discord.TextChannel)

        game_data = {
            "posts": [
                {
                    "guild_xid": 99999,
                    "channel_xid": 88888,
                    "message_xid": 77777,
                },
            ],
        }

        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_text_channel",
            AsyncMock(return_value=mock_channel),
        )
        mocker.patch("spellbot.actions.lfg_action.safe_get_partial_message", return_value=None)
        update_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(),
        )

        await action._handle_embed_creation(new=False, origin=True, fully_seated=False)

        update_stub.assert_not_called()

    async def test_handle_embed_creation_update_fails(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_embed_creation continues when update fails."""
        mock_embed = MagicMock(spec=discord.Embed)
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        game_data = {
            "posts": [
                {
                    "guild_xid": 99999,
                    "channel_xid": 88888,
                    "message_xid": 77777,
                },
            ],
        }

        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_text_channel",
            AsyncMock(return_value=mock_channel),
        )
        mocker.patch(
            "spellbot.actions.lfg_action.safe_get_partial_message",
            return_value=mock_message,
        )
        # Update returns False, meaning it failed
        mocker.patch(
            "spellbot.actions.lfg_action.safe_update_embed",
            AsyncMock(return_value=False),
        )

        # Should not raise an exception, just continue
        await action._handle_embed_creation(new=False, origin=True, fully_seated=False)

    async def test_reply_found_embed_no_jump_link(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _reply_found_embed when no jump link for current guild."""
        game_data = {
            "id": 123,
            "format": 1,
            "jump_links": {},  # No jump links
        }

        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        followup_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_followup_channel",
            AsyncMock(),
        )

        await action._reply_found_embed()

        followup_stub.assert_called_once()
        # Check the embed description contains the game ID
        call_args = followup_stub.call_args
        embed = call_args.kwargs["embed"]
        assert "SB123" in embed.description

    async def test_handle_direct_messages_with_pin(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_direct_messages sends DMs with mythic track link when PIN exists."""
        mock_user = MagicMock(spec=discord.User)
        mock_embed = MagicMock(spec=discord.Embed)
        mock_embed.description = "Game started!"
        mock_embed.copy = MagicMock(return_value=mock_embed)

        game_data = {
            "id": 1,
            "format": 1,
            "service": 1,
            "bracket": 2,
            "jump_links": {},
        }

        # Player has a PIN
        mocker.patch.object(
            action.services.games,
            "player_pins",
            AsyncMock(return_value={123: "ABC123"}),
        )
        mocker.patch.object(
            action.services.games,
            "player_names",
            AsyncMock(return_value={123: "TestPlayer"}),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_user",
            AsyncMock(return_value=mock_user),
        )
        send_stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())
        mocker.patch.object(action.services.awards, "give_awards", AsyncMock(return_value={}))

        await action._handle_direct_messages()

        send_stub.assert_called_once()
        # Verify Mythic Track link was added to description
        assert "Mythic Track" in mock_embed.description

    async def test_handle_direct_messages_award_to_unfetched_player(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_direct_messages warns when award goes to unfetched player."""
        mock_embed = MagicMock(spec=discord.Embed)
        mock_embed.description = "Game started!"
        mock_embed.copy = MagicMock(return_value=mock_embed)

        game_data = {
            "id": 1,
            "format": 1,
            "service": 1,
            "bracket": 2,
            "jump_links": {},
        }

        # Player cannot be fetched
        mocker.patch.object(
            action.services.games,
            "player_pins",
            AsyncMock(return_value={123: None}),
        )
        mocker.patch.object(
            action.services.games,
            "player_names",
            AsyncMock(return_value={123: "TestPlayer"}),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch("spellbot.actions.lfg_action.safe_fetch_user", AsyncMock(return_value=None))
        mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())

        # Award for unfetched player
        new_award = NewAward(role="SomeRole", message="Congrats!", remove=False)
        mocker.patch.object(
            action.services.awards,
            "give_awards",
            AsyncMock(return_value={123: [new_award]}),
        )
        followup_stub = mocker.patch(
            "spellbot.actions.lfg_action.safe_followup_channel",
            AsyncMock(),
        )

        await action._handle_direct_messages()

        # Should have 2 calls:
        # 1. "Unable to give role 999 to user <@123>"
        # 2. "Unable to send Direct Messages to some players: <@!123>"
        assert followup_stub.call_count == 2
        first_call = followup_stub.call_args_list[0]
        assert "Unable to give" in first_call[0][1]

    async def test_handle_direct_messages_award_success(
        self,
        action: LookingForGameAction,
        mocker: MockerFixture,
    ) -> None:
        """Test _handle_direct_messages gives awards to fetched players."""
        mock_user = MagicMock(spec=discord.User)
        mock_embed = MagicMock(spec=discord.Embed)
        mock_embed.description = "Game started!"
        mock_embed.copy = MagicMock(return_value=mock_embed)

        game_data = {
            "id": 1,
            "format": 1,
            "service": 1,
            "bracket": 2,
            "jump_links": {},
        }

        mocker.patch.object(
            action.services.games,
            "player_pins",
            AsyncMock(return_value={123: None}),
        )
        mocker.patch.object(
            action.services.games,
            "player_names",
            AsyncMock(return_value={123: "TestPlayer"}),
        )
        mocker.patch.object(action.services.games, "to_dict", AsyncMock(return_value=game_data))
        mocker.patch.object(action.services.games, "to_embed", AsyncMock(return_value=mock_embed))
        mocker.patch(
            "spellbot.actions.lfg_action.safe_fetch_user",
            AsyncMock(return_value=mock_user),
        )
        send_stub = mocker.patch("spellbot.actions.lfg_action.safe_send_user", AsyncMock())
        add_role_stub = mocker.patch("spellbot.actions.lfg_action.safe_add_role", AsyncMock())

        # Award for fetched player
        new_award = NewAward(role="SomeRole", message="Congrats!", remove=False)
        mocker.patch.object(
            action.services.awards,
            "give_awards",
            AsyncMock(return_value={123: [new_award]}),
        )

        await action._handle_direct_messages()

        # Should give role
        add_role_stub.assert_called_once()
        # Should send award message
        assert send_stub.call_count >= 2  # One for game DM, one for award message

    async def test_get_bracket_when_no_format_no_bracket_no_default(
        self,
        action: LookingForGameAction,
    ) -> None:
        action.channel_data = {"default_bracket": None}  # type: ignore
        assert await action.get_bracket(None, None) == GameBracket.NONE.value
