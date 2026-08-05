from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import discord
import pytest
import pytest_asyncio

from spellbot import services
from spellbot.actions import leave_action, lfg_action, web_action
from spellbot.actions.web_action import WebLeaveAction, WebLookingForGameAction
from spellbot.database import DatabaseSession
from spellbot.enums import GameFormat
from spellbot.models import Game, GameStatus
from spellbot.views import GameView
from tests.mocks import build_author, build_channel, build_guild, mock_operations

if TYPE_CHECKING:
    from spellbot import SpellBot
    from spellbot.models import Channel, Guild, User
    from tests.fixtures import Factories

pytestmark = pytest.mark.use_db


# The shared `guild` / `channel` / `user` fixtures are database rows keyed off the
# interaction fixture. A website action is driven by resolved discord.py objects
# instead, so build ones that point at those same rows.


@pytest.fixture
def web_guild(guild: Guild) -> discord.Guild:
    built = build_guild()
    built.id = cast("int", guild.xid)
    return built


@pytest.fixture
def web_channel(web_guild: discord.Guild, channel: Channel) -> discord.TextChannel:
    built = build_channel(web_guild)
    built.id = cast("int", channel.xid)
    return built


@pytest.fixture
def web_member(user: User) -> discord.User:
    member = build_author()
    member.id = cast("int", user.xid)
    return member


@pytest_asyncio.fixture
async def lfg(
    bot: SpellBot,
    web_guild: discord.Guild,
    web_channel: discord.TextChannel,
    web_member: discord.User,
) -> WebLookingForGameAction:
    async with WebLookingForGameAction.create_for_web(
        bot,
        actor=web_member,
        guild=web_guild,
        channel=web_channel,
        locale="en",
        request_id="web-action-1",
    ) as action:
        return action


@pytest.mark.asyncio
class TestWebActionMixin:
    async def test_has_no_interaction(self, lfg: WebLookingForGameAction) -> None:
        # Leaving `interaction` unset is what makes a missed call site fail loudly
        # instead of quietly doing the wrong thing.
        assert not hasattr(lfg, "interaction")

    async def test_accessors_read_from_the_web_request(
        self,
        lfg: WebLookingForGameAction,
        web_guild: discord.Guild,
        web_member: discord.User,
    ) -> None:
        assert lfg.actor is web_member
        assert lfg.guild_xid == web_guild.id
        assert lfg.origin_message is None
        assert lfg.locale == "en"

    async def test_reply_is_captured_as_a_notice(self, lfg: WebLookingForGameAction) -> None:
        assert await lfg.reply("something happened") is None
        assert lfg.notices == ["something happened"]

    async def test_reply_captures_an_embed_description(
        self,
        lfg: WebLookingForGameAction,
    ) -> None:
        embed = discord.Embed(description="your game is ready")
        await lfg.reply(embed=embed)
        assert lfg.notices == ["your game is ready"]

    async def test_reply_falls_back_to_the_embed_author(
        self,
        lfg: WebLookingForGameAction,
    ) -> None:
        embed = discord.Embed()
        embed.set_author(name="Found your game!")
        await lfg.reply(embed=embed)
        assert lfg.notices == ["Found your game!"]

    async def test_notify_actor_does_not_dm(self, lfg: WebLookingForGameAction) -> None:
        # The user is looking at the website, so the message belongs there — and a DM
        # would spend a slot from the budget real game-details DMs share.
        with mock_operations(web_action):
            await lfg.notify_actor("you can not join that game")
            assert lfg.notices == ["you can not join that game"]

    async def test_update_origin_is_a_no_op(self, lfg: WebLookingForGameAction) -> None:
        assert await lfg.update_origin(embed=discord.Embed()) is False

    async def test_origin_response_is_none(self, lfg: WebLookingForGameAction) -> None:
        assert await lfg.origin_response() is None

    async def test_post_game_message_defers_to_the_channel(
        self,
        lfg: WebLookingForGameAction,
    ) -> None:
        # Returning None is what makes `create_initial_post` fall through to
        # `safe_channel_reply`, which is the only way a web action can post at all.
        assert await lfg.post_game_message(embed=discord.Embed()) is None

    async def test_warn_channel_still_posts_to_discord(
        self,
        lfg: WebLookingForGameAction,
        web_channel: discord.TextChannel,
    ) -> None:
        # This warning names other players so they learn their DMs are closed; it must
        # not be swallowed into a notice only the acting user would ever see.
        with mock_operations(web_action):
            await lfg.warn_channel("I could not DM <@!123>")
            web_action.safe_channel_reply.assert_called_once_with(
                web_channel,
                "I could not DM <@!123>",
            )
        assert lfg.notices == ["I could not DM <@!123>"]


@pytest.mark.asyncio
class TestWebLookingForGameAction:
    async def test_create_posts_the_game_to_the_channel(
        self,
        lfg: WebLookingForGameAction,
        web_channel: discord.TextChannel,
    ) -> None:
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 5001
            lfg_action.safe_channel_reply.return_value = message

            await lfg.execute(format=GameFormat.MODERN.value)

            # The interaction-based path is unavailable, so the game must arrive via a
            # plain channel send — with the Join/Leave view still attached.
            lfg_action.safe_channel_reply.assert_called_once()
            call = lfg_action.safe_channel_reply.call_args
            assert call.args[0] is web_channel
            assert isinstance(call.kwargs["view"], GameView)
            lfg_action.safe_followup_channel.assert_not_called()

        DatabaseSession.expire_all()
        game = (await DatabaseSession.execute(Game.__table__.select())).first()
        assert game is not None
        assert lfg.game_id is not None

    async def test_create_records_the_post_so_the_game_is_reachable(
        self,
        lfg: WebLookingForGameAction,
    ) -> None:
        # A game with no post is invisible in Discord and gets silently reaped later,
        # so the fallback send must still be recorded as the game's post.
        with mock_operations(lfg_action):
            message = MagicMock(spec=discord.Message)
            message.id = 5002
            lfg_action.safe_channel_reply.return_value = message
            await lfg.execute()

        assert lfg.game_id is not None
        game_data = await services.games.get(lfg.game_id)
        assert game_data is not None
        assert [post.message_xid for post in game_data.posts] == [5002]

    async def test_join_by_game_id(
        self,
        lfg: WebLookingForGameAction,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        other = factories.user.create(xid=880001, name="Other")
        game = factories.game.create(guild=guild, channel=channel, seats=4)
        factories.queue.create(user_xid=other.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.post.create(
            game=game,
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            message_xid=5100,
        )

        with mock_operations(lfg_action):
            lfg_action.safe_get_partial_message.return_value = MagicMock()
            await lfg.execute(game_id=game.id)

        DatabaseSession.expire_all()
        found = await services.games.get(game.id)
        assert found is not None
        assert {player.xid for player in found.players} == {other.xid, user.xid}

    async def test_join_refuses_a_game_in_another_channel(
        self,
        lfg: WebLookingForGameAction,
        factories: Factories,
        guild: Guild,
        user: User,
    ) -> None:
        # The id arrives from the request, so it must not be able to reach a game the
        # viewer was never offered.
        elsewhere = factories.channel.create(xid=880002, guild=guild, name="elsewhere")
        game = factories.game.create(guild=guild, channel=elsewhere, seats=4)

        with mock_operations(lfg_action):
            await lfg.execute(game_id=game.id)

        DatabaseSession.expire_all()
        found = await services.games.get(game.id)
        assert found is not None
        assert user.xid not in {player.xid for player in found.players}
        assert lfg.notices  # the user is told they can not join

    async def test_join_refuses_a_started_game(
        self,
        lfg: WebLookingForGameAction,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        game = factories.game.create(
            guild=guild,
            channel=channel,
            seats=4,
            status=GameStatus.STARTED.value,
        )

        with mock_operations(lfg_action):
            await lfg.execute(game_id=game.id)

        DatabaseSession.expire_all()
        found = await services.games.get(game.id)
        assert found is not None
        assert user.xid not in {player.xid for player in found.players}


@pytest.mark.asyncio
class TestWebLeaveAction:
    async def test_leave_removes_the_player(
        self,
        bot: SpellBot,
        web_guild: discord.Guild,
        web_channel: discord.TextChannel,
        web_member: discord.User,
        factories: Factories,
        guild: Guild,
        channel: Channel,
        user: User,
    ) -> None:
        other = factories.user.create(xid=880003, name="Other")
        game = factories.game.create(guild=guild, channel=channel, seats=4)
        factories.queue.create(user_xid=user.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.queue.create(user_xid=other.xid, game_id=game.id, og_guild_xid=guild.xid)
        factories.post.create(
            game=game,
            guild_xid=guild.xid,
            channel_xid=channel.xid,
            message_xid=5200,
        )

        with mock_operations(leave_action):
            leave_action.safe_get_partial_message.return_value = MagicMock()
            async with WebLeaveAction.create_for_web(
                bot,
                actor=web_member,
                guild=web_guild,
                channel=web_channel,
                locale="en",
                request_id="web-action-2",
            ) as action:
                await action.execute()
                # There is no interaction to answer, so the confirmation is a notice.
                assert action.notices
                leave_action.safe_send_channel.assert_not_called()

        DatabaseSession.expire_all()
        found = await services.games.get(game.id)
        assert found is not None
        assert {player.xid for player in found.players} == {other.xid}
