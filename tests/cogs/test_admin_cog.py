from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import discord
import pytest
import pytest_asyncio
from sqlalchemy import select, update

from spellbot.actions import admin_action
from spellbot.cogs import AdminCog
from spellbot.database import DatabaseSession
from spellbot.enums import GameBracket
from spellbot.models import Channel, Game, Guild
from tests.fixtures import get_last_send_message, run_command
from tests.mocks import mock_operations

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.settings import Settings
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


@pytest_asyncio.fixture
async def cog(bot: SpellBot) -> AdminCog:
    return AdminCog(bot)


@pytest.mark.asyncio
class TestCogAdminSetup:
    async def test_setup(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        settings: Settings,
    ) -> None:
        await run_command(cog.setup, interaction)

        embed = get_last_send_message(interaction, "embed")
        assert embed["title"] == f"SpellBot Setup for {guild.name}"
        assert embed["color"] == settings.INFO_EMBED_COLOR
        assert embed["thumbnail"]["url"] == settings.ICO_URL
        assert f"{settings.API_BASE_URL}/g/{guild.xid}" in embed["description"]
        assert "fields" not in embed
        assert "view" not in interaction.response.send_message.call_args.kwargs  # type: ignore


@pytest.mark.asyncio
class TestCogAdminGameInfo:
    async def test_happy_path(
        self,
        cog: AdminCog,
        game: Game,
        interaction: discord.Interaction,
        settings: Settings,
    ) -> None:
        await run_command(cog.game_info, interaction, game_id=f"SB#{game.id}")
        embed = get_last_send_message(interaction, "embed")
        assert embed["author"]["name"] == f"Game info for #SB{game.id}"
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["Format"] == "Commander"
        assert fields["Players"] == "0/4"
        assert fields["Started at"] == "Not started yet"
        assert "Bracket" not in fields
        assert fields["Details"] == (
            f"[View on spellbot.io]({settings.API_BASE_URL}/game/{game.id})"
        )
        assert get_last_send_message(interaction, "ephemeral") is True

    async def test_started_game_with_bracket(
        self,
        cog: AdminCog,
        guild: Guild,
        channel: Channel,
        interaction: discord.Interaction,
        factories: Factories,
    ) -> None:
        started_at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=2,
            bracket=GameBracket.BRACKET_1.value,
            started_at=started_at,
        )
        player = factories.user.create()
        factories.play.create(user_xid=player.xid, game_id=game.id, og_guild_xid=guild.xid)

        await run_command(cog.game_info, interaction, game_id=str(game.id))
        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["Bracket"] == "Bracket 1: Exhibition"
        assert fields["Players"] == "1/2"
        # A started game shows a Discord timestamp for when it began.
        assert fields["Started at"] == f"<t:{int(started_at.timestamp())}>"

    async def test_non_numeric_game_id(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await run_command(cog.game_info, interaction, game_id="bogus")
        interaction.response.send_message.assert_awaited_once_with(  # type: ignore
            "There is no game with that ID.",
            ephemeral=True,
        )

    async def test_non_existant_game_id(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await run_command(cog.game_info, interaction, game_id="1")
        interaction.response.send_message.assert_awaited_once_with(  # type: ignore
            "There is no game with that ID.",
            ephemeral=True,
        )


@pytest.mark.asyncio
class TestCogAdminMythicTrack:
    @pytest.mark.parametrize("initial_setting", [True, False])
    async def test_setup_mythic_track(
        self,
        cog: AdminCog,
        initial_setting: bool,
        interaction: discord.Interaction,
        guild: Guild,
    ) -> None:
        await DatabaseSession.execute(
            update(Guild).where(Guild.xid == guild.xid).values(enable_mythic_track=initial_setting),  # type: ignore
        )
        await DatabaseSession.commit()

        await run_command(cog.setup_mythic_track, interaction)

        interaction.response.send_message.assert_called_once()  # type: ignore
        db_guild = (await DatabaseSession.execute(select(Guild))).scalar_one()
        assert db_guild.enable_mythic_track != initial_setting


@pytest.mark.asyncio
class TestCogAdminExpireGames:
    async def test_no_games_to_expire(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        mocker: MockerFixture,
    ) -> None:
        with mock_operations(admin_action):
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)
            admin_action.safe_send_channel.assert_called_once()
            call_args = admin_action.safe_send_channel.call_args
            assert call_args[0][1] == "No games to expire."

    async def test_expire_game_with_post_deleted(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild, delete_expired=True)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=1234)
        factories.user.create(game=game)

        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = mock_channel
            admin_action.safe_get_partial_message.return_value = mock_message
            admin_action.safe_delete_message.return_value = True
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            admin_action.safe_delete_message.assert_called_once_with(mock_message)
            call_args = admin_action.safe_send_channel.call_args
            assert f"Expiring game #SB{game.id}" in call_args[0][1]
            assert "Deleting message 1234" in call_args[0][1]
            assert "Done" in call_args[0][1]

    async def test_expire_game_with_post_updated(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild, delete_expired=False)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=5678)
        factories.user.create(game=game)

        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = mock_channel
            admin_action.safe_get_partial_message.return_value = mock_message
            admin_action.safe_update_embed.return_value = True
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            admin_action.safe_update_embed.assert_called_once_with(
                mock_message,
                content="Sorry, this game was expired due to inactivity.",
                embed=None,
                view=None,
            )
            call_args = admin_action.safe_send_channel.call_args
            assert "Updating message 5678" in call_args[0][1]

    async def test_expire_game_channel_not_found(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=9999)
        factories.user.create(game=game)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = None
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            call_args = admin_action.safe_send_channel.call_args
            assert f"Could not find channel {channel.xid}" in call_args[0][1]

    async def test_expire_game_message_not_found(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=7777)
        factories.user.create(game=game)

        mock_channel = MagicMock(spec=discord.TextChannel)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = mock_channel
            admin_action.safe_get_partial_message.return_value = None
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            call_args = admin_action.safe_send_channel.call_args
            assert "Could not find message 7777" in call_args[0][1]

    async def test_expire_game_delete_no_permission(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild, delete_expired=True)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=1111)
        factories.user.create(game=game)

        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = mock_channel
            admin_action.safe_get_partial_message.return_value = mock_message
            admin_action.safe_delete_message.return_value = False
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            call_args = admin_action.safe_send_channel.call_args
            assert "Bot does not have permission" in call_args[0][1]

    async def test_expire_game_update_no_permission(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild, delete_expired=False)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=2222)
        factories.user.create(game=game)

        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = mock_channel
            admin_action.safe_get_partial_message.return_value = mock_message
            admin_action.safe_update_embed.return_value = False
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            call_args = admin_action.safe_send_channel.call_args
            assert "Bot does not have permission" in call_args[0][1]

    async def test_expire_game_no_posts(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        channel = factories.channel.create(guild=guild)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        # No posts created for this game
        factories.user.create(game=game)

        with mock_operations(admin_action):
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            call_args = admin_action.safe_send_channel.call_args
            assert f"Expiring game #SB{game.id}" in call_args[0][1]
            assert "Dequeued" in call_args[0][1]

    async def test_expire_game_deletes_when_no_players_dequeued(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        mocker: MockerFixture,
    ) -> None:
        """When dequeued=0, should delete message even if delete_expired=False."""
        channel = factories.channel.create(guild=guild, delete_expired=False)
        old_date = datetime.now(tz=UTC) - timedelta(days=1)
        game = factories.game.create(guild=guild, channel=channel, updated_at=old_date)
        factories.post.create(guild=guild, channel=channel, game=game, message_xid=3333)
        # No users in game, so dequeued will be 0

        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock(spec=discord.PartialMessage)

        with mock_operations(admin_action):
            admin_action.safe_fetch_text_channel.return_value = mock_channel
            admin_action.safe_get_partial_message.return_value = mock_message
            admin_action.safe_delete_message.return_value = True
            admin_action.safe_send_channel.return_value = True
            await run_command(cog.expire_games, interaction)

            # Should delete because dequeued=0
            admin_action.safe_delete_message.assert_called_once()
            call_args = admin_action.safe_send_channel.call_args
            assert "Deleting message 3333" in call_args[0][1]


@pytest.mark.asyncio
class TestCogAdminUserInfo:
    async def test_user_info_happy_path(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
        settings: Settings,
    ) -> None:
        """Test basic user info with games, blocks, and various states."""
        # Create target user
        target_user = factories.user.create(xid=9001, name="TargetUser")

        # Create some games with plays
        game1 = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )
        game2 = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime(2026, 3, 20, 14, 0, 0, tzinfo=UTC),
        )
        factories.play.create(
            user_xid=target_user.xid,
            game_id=game1.id,
            og_guild_xid=guild.xid,
        )
        factories.play.create(
            user_xid=target_user.xid,
            game_id=game2.id,
            og_guild_xid=guild.xid,
        )

        # Create blocks against the target
        blocker1 = factories.user.create()
        blocker2 = factories.user.create()
        factories.block.create(user_xid=blocker1.xid, blocked_user_xid=target_user.xid)
        factories.block.create(user_xid=blocker2.xid, blocked_user_xid=target_user.xid)

        # Create verification and watch
        factories.verify.create(user_xid=target_user.xid, guild_xid=guild.xid, verified=True)
        factories.watch.create(user_xid=target_user.xid, guild_xid=guild.xid, note="Suspicious")

        # Mock the discord user
        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "TargetUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        assert embed["author"]["name"] == "User info for TargetUser"
        assert embed["color"] == settings.INFO_EMBED_COLOR
        assert embed["footer"]["text"] == f"User ID: {target_user.xid}"

        # Check fields
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert f"2 games on {guild.name}" in fields["Games Played"]
        assert "Blocked by 2 users" in fields["Block Status"]
        assert "✅ Verified" in fields["Verified"]
        assert "⚠️ Watched: Suspicious" in fields["Watch Status"]
        assert "2025-01-15 to 2026-03-20" in fields["Play Range"]
        assert fields["Game History"] == (
            f"[View on spellbot.io]({settings.API_BASE_URL}/g/{guild.xid}/u/{target_user.xid})"
        )

    async def test_user_info_no_games(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
        settings: Settings,
    ) -> None:
        """Test user info when user has no games."""
        target_user = factories.user.create(xid=9002, name="NoGamesUser")

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "NoGamesUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert f"0 games on {guild.name}" in fields["Games Played"]
        assert "Blocked by 0 users" in fields["Block Status"]
        assert "No games played" in fields["Play Range"]

    async def test_user_info_single_game(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        channel: Channel,
        factories: Factories,
    ) -> None:
        """Test user info with a single game (same date range)."""
        target_user = factories.user.create(xid=9003)

        game = factories.game.create(
            guild=guild,
            channel=channel,
            started_at=datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
        )
        factories.play.create(
            user_xid=target_user.xid,
            game_id=game.id,
            og_guild_xid=guild.xid,
        )

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "SingleGameUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert "1 game on" in fields["Games Played"]  # singular
        assert "2025-06-01" in fields["Play Range"]
        assert "to" not in fields["Play Range"]  # same day, no range

    async def test_user_info_single_block(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        """Test user info with exactly 1 block (singular)."""
        target_user = factories.user.create(xid=9004)
        blocker = factories.user.create()
        factories.block.create(user_xid=blocker.xid, blocked_user_xid=target_user.xid)

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "SingleBlockUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert "Blocked by 1 user" in fields["Block Status"]  # singular

    async def test_user_info_verified_false(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        """Test user info when user is explicitly unverified."""
        target_user = factories.user.create(xid=9005)
        factories.verify.create(user_xid=target_user.xid, guild_xid=guild.xid, verified=False)

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "UnverifiedUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert "❌ Unverified" in fields["Verified"]

    async def test_user_info_verified_not_set(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        """Test user info when user has no verification record."""
        target_user = factories.user.create(xid=9006)
        # No verify record created

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "NoVerifyUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert "Not set" in fields["Verified"]

    async def test_user_info_watched_no_note(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        """Test user info when user is watched without a note."""
        target_user = factories.user.create(xid=9007)
        factories.watch.create(user_xid=target_user.xid, guild_xid=guild.xid, note="")

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "WatchedNoNoteUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert fields["Watch Status"] == "⚠️ Watched"

    async def test_user_info_not_watched(
        self,
        cog: AdminCog,
        interaction: discord.Interaction,
        guild: Guild,
        factories: Factories,
    ) -> None:
        """Test user info when user is not watched."""
        target_user = factories.user.create(xid=9008)
        # No watch record created

        mock_target = MagicMock(spec=discord.User)
        mock_target.id = target_user.xid
        mock_target.display_name = "NotWatchedUser"

        await run_command(cog.user_info, interaction, target=mock_target)

        embed = get_last_send_message(interaction, "embed")
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        assert "Not watched" in fields["Watch Status"]
