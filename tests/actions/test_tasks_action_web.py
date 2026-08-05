from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from spellbot import services
from spellbot.actions import tasks_action
from spellbot.actions.tasks_action import TasksAction
from spellbot.database import DatabaseSession
from spellbot.errors import GuildBannedError, UserBannedError, UserVerifiedError
from spellbot.models import WebActionError, WebActionKind, WebActionStatus
from tests.mocks import build_author, build_channel, build_guild

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from spellbot import SpellBot
    from spellbot.models import Channel, Guild, User
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db

PLAYABLE = discord.Permissions(
    view_channel=True,
    send_messages=True,
    use_application_commands=True,
)
NO_COMMANDS = discord.Permissions(view_channel=True, send_messages=True)


@pytest.fixture
def web_guild(guild: Guild) -> discord.Guild:
    built = build_guild()
    built.id = cast("int", guild.xid)
    return built


@pytest.fixture
def web_channel(web_guild: discord.Guild, channel: Channel) -> discord.TextChannel:
    built = build_channel(web_guild)
    built.id = cast("int", channel.xid)
    built.permissions_for = MagicMock(return_value=PLAYABLE)
    return built


@pytest.fixture
def web_member(user: User) -> discord.User:
    member = build_author()
    member.id = cast("int", user.xid)
    return member


@pytest.fixture
def wired(
    mocker: MockerFixture,
    bot: SpellBot,
    web_guild: discord.Guild,
    web_channel: discord.TextChannel,
    web_member: discord.User,
) -> None:
    """Resolve every Discord lookup the worker makes to our fixtures, by default."""
    mocker.patch.object(type(bot), "guilds", [web_guild], create=True)
    mocker.patch.object(tasks_action, "safe_fetch_guild", AsyncMock(return_value=web_guild))
    mocker.patch.object(
        tasks_action,
        "safe_fetch_text_channel",
        AsyncMock(return_value=web_channel),
    )
    mocker.patch.object(tasks_action, "safe_fetch_member", AsyncMock(return_value=web_member))
    mocker.patch.object(tasks_action, "bot_can_send_messages", MagicMock(return_value=True))


async def enqueue(
    guild: Guild,
    channel: Channel,
    user: User,
    *,
    kind: str = WebActionKind.CREATE.value,
    game_id: int | None = None,
) -> int:
    action = await services.web_actions.enqueue(
        user_xid=cast("int", user.xid),
        guild_xid=guild.xid,
        channel_xid=channel.xid,
        kind=kind,
        locale="en",
        game_id=game_id,
    )
    return action.id


async def outcome(action_id: int, user: User) -> tuple[str, str | None]:
    DatabaseSession.expire_all()
    found = await services.web_actions.get(action_id, user_xid=cast("int", user.xid))
    assert found is not None
    return found.status, found.error_code


@pytest.mark.asyncio
@pytest.mark.usefixtures("wired")
class TestProcessWebActions:
    async def test_a_create_request_posts_a_game(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        message = MagicMock(spec=discord.Message)
        message.id = 7001
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "spellbot.actions.lfg_action.safe_channel_reply",
                AsyncMock(return_value=message),
            )
            async with TasksAction.create(bot) as action:
                await action.process_web_actions()

        status, error = await outcome(action_id, user)
        assert (status, error) == (WebActionStatus.DONE.value, None)
        found = await services.web_actions.get(action_id, user_xid=cast("int", user.xid))
        assert found is not None
        assert found.game_id is not None

    async def test_missing_guild_is_reported(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        mocker.patch.object(tasks_action, "safe_fetch_guild", AsyncMock(return_value=None))
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.GUILD_UNAVAILABLE.value,
        )

    async def test_missing_channel_is_reported(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        mocker.patch.object(tasks_action, "safe_fetch_text_channel", AsyncMock(return_value=None))
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.CHANNEL_UNAVAILABLE.value,
        )

    async def test_a_user_who_left_the_server_is_refused(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        # This is the check the website can not make reliably: by the time the bot acts,
        # the user may have been kicked or banned since the page was rendered.
        action_id = await enqueue(guild, channel, user)
        mocker.patch.object(tasks_action, "safe_fetch_member", AsyncMock(return_value=None))
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.NOT_A_MEMBER.value,
        )

    async def test_missing_channel_permissions_are_refused(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
        web_channel: discord.TextChannel,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        web_channel.permissions_for = MagicMock(return_value=NO_COMMANDS)
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.MISSING_PERMISSIONS.value,
        )

    async def test_a_channel_the_bot_cannot_post_in_is_refused(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        mocker.patch.object(tasks_action, "bot_can_send_messages", MagicMock(return_value=False))
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.BOT_MISSING_PERMISSIONS.value,
        )

    async def test_a_server_that_turned_the_feature_off_is_refused(
        self,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        await services.guilds.update_settings(guild.xid, web_games=False)
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.WEB_GAMES_DISABLED.value,
        )

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            pytest.param(GuildBannedError(), WebActionError.GUILD_BANNED.value, id="guild_banned"),
            pytest.param(UserBannedError(), WebActionError.USER_BANNED.value, id="user_banned"),
            pytest.param(
                UserVerifiedError(),
                WebActionError.CHANNEL_UNVERIFIED_ONLY.value,
                id="unverified_only",
            ),
        ],
    )
    async def test_rejections_map_to_stable_codes(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
        error: Exception,
        expected: str,
    ) -> None:
        action_id = await enqueue(guild, channel, user)
        mocker.patch(
            "spellbot.actions.base_action.BaseAction.upsert_request_objects",
            AsyncMock(side_effect=error),
        )
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (WebActionStatus.ERROR.value, expected)

    async def test_an_unexpected_failure_is_reported_not_swallowed(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        # A crash must still resolve the row, or the page spins until the stale sweep.
        action_id = await enqueue(guild, channel, user)
        mocker.patch.object(
            TasksAction,
            "run_web_lfg",
            AsyncMock(side_effect=RuntimeError("boom")),
        )
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (
            WebActionStatus.ERROR.value,
            WebActionError.INTERNAL_ERROR.value,
        )

    async def test_requests_for_other_guilds_are_left_alone(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        # A shard that is not in the guild must leave the row for one that is.
        action_id = await enqueue(guild, channel, user)
        mocker.patch.object(type(bot), "guilds", [], create=True)
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        assert await outcome(action_id, user) == (WebActionStatus.PENDING.value, None)

    async def test_the_guild_lock_is_held_while_acting(
        self,
        mocker: MockerFixture,
        bot: SpellBot,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        # Without this, a website join and a Discord button click on the same game can
        # race through `add_player` and over-seat it.
        action_id = await enqueue(guild, channel, user)
        lock = MagicMock()
        lock.__aenter__ = AsyncMock()
        lock.__aexit__ = AsyncMock(return_value=False)
        guild_lock = mocker.patch.object(type(bot), "guild_lock", MagicMock(return_value=lock))
        mocker.patch.object(TasksAction, "run_web_lfg", AsyncMock(return_value=(None, None, [])))
        async with TasksAction.create(bot) as action:
            await action.process_web_actions()
        guild_lock.assert_called_once_with(guild.xid)
        lock.__aenter__.assert_awaited_once()
        assert await outcome(action_id, user) == (WebActionStatus.DONE.value, None)

    async def test_a_leave_request_removes_the_player(
        self,
        bot: SpellBot,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        user: User,
        web_channel: discord.TextChannel,
    ) -> None:
        other = factories.user.create(xid=870001, name="Other")
        game = factories.game.create(guild=guild, channel=channel, seats=4)
        factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=other.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.post.create(
            game=game,
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            message_xid=7100,
        )
        action_id = await enqueue(
            guild,
            channel,
            user,
            kind=WebActionKind.LEAVE.value,
            game_id=game.id,
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "spellbot.actions.leave_action.safe_fetch_text_channel",
                AsyncMock(return_value=web_channel),
            )
            mp.setattr(
                "spellbot.actions.leave_action.safe_get_partial_message",
                MagicMock(return_value=MagicMock()),
            )
            mp.setattr("spellbot.actions.leave_action.safe_update_embed", AsyncMock())
            async with TasksAction.create(bot) as action:
                await action.process_web_actions()

        assert await outcome(action_id, user) == (WebActionStatus.DONE.value, None)
        DatabaseSession.expire_all()
        found = await services.games.get(game.id)
        assert found is not None
        assert {player.xid for player in found.players} == {other.xid}
